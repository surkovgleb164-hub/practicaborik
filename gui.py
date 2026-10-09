"""Интерфейс Tkinter: клиника «Дентал+».
Роли: admin — всё; doctor — приёмы и пациенты; registrator — пациенты и запись;
accountant — платежи и отчёты."""
import sqlite3
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

from .db import connect
from .models import (validate_appointment, validate_patient, validate_payment)
from .security import verify

PAGE = 10
REPORTS = [
    "Приёмы по месяцам",
    "Загрузка врачей",
    "Топ-10 услуг",
    "Должники",
    "Выручка за период",
]


class Session:
    name, role = "", ""


def err_text(e):
    return getattr(e, "msg", None) or str(e)


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход — Дентал+")
        self.resizable(False, False)
        self.tries, self.ok = 0, False
        f = ttk.Frame(self, padding=20)
        f.pack()
        ttk.Label(f, text="Логин").pack(anchor="w")
        self.login = ttk.Entry(f, width=30)
        self.login.pack(pady=4)
        ttk.Label(f, text="Пароль").pack(anchor="w")
        self.pw = ttk.Entry(f, width=30, show="*")
        self.pw.pack(pady=4)
        self.err = ttk.Label(f, foreground="crimson", wraplength=260)
        self.err.pack()
        ttk.Button(f, text="Войти", command=self.submit).pack(pady=6)
        self.bind("<Return>", lambda e: self.submit())
        self.login.focus()

    def submit(self):
        try:
            with connect() as c:
                u = c.execute(
                    "SELECT full_name, role, password_hash FROM employees WHERE login = ?",
                    (self.login.get(),),
                ).fetchone()
            if u and verify(self.pw.get(), u["password_hash"]):
                Session.name, Session.role = u["full_name"], u["role"]
                self.ok = True
                self.destroy()
                return
        except sqlite3.Error as e:
            self.err["text"] = f"Ошибка БД: {e}"
            return
        self.tries += 1
        self.err["text"] = "Неверный логин или пароль"
        if self.tries >= 3:
            self.destroy()


def _lookups():
    with connect() as c:
        return {
            "patients":  [(r["id"], r["full_name"]) for r in c.execute("SELECT id, full_name FROM patients ORDER BY full_name")],
            "doctors":   [(r["id"], r["full_name"]) for r in c.execute("SELECT id, full_name FROM doctors WHERE active=1 ORDER BY full_name")],
            "cabinets":  [(r["id"], f'{r["number"]} — {r["name"] or ""}') for r in c.execute("SELECT id, number, name FROM cabinets ORDER BY number")],
            "diagnoses": [(r["id"], f'{r["code"]} {r["name"]}') for r in c.execute("SELECT id, code, name FROM diagnoses ORDER BY code")],
            "services":  [(r["id"], f'{r["code"]} {r["name"]} ({r["price"]:.0f} ₽)') for r in c.execute("SELECT id, code, name, price FROM services ORDER BY name")],
        }


class AppointmentForm(tk.Toplevel):
    SPECS = [
        ("Пациент", "patient_id", "patients"),
        ("Врач", "doctor_id", "doctors"),
        ("Кабинет", "cabinet_id", "cabinets"),
        ("Диагноз", "diagnosis_id", "diagnoses"),
        ("Дата (ГГГГ-ММ-ДД)", "visit_date", None),
        ("Время (ЧЧ:ММ)", "visit_time", None),
        ("Статус", "status", None),
        ("Жалобы", "complaint", None),
    ]
    STATUSES = ("planned", "done", "cancelled", "no_show")

    def __init__(self, parent, appointment=None):
        super().__init__(parent)
        self.title("Редактирование приёма" if appointment else "Новый приём")
        self.resizable(False, False)
        self.result, self.lk, self.w = None, _lookups(), {}
        f = ttk.Frame(self, padding=14)
        f.pack()
        for label, key, lk in self.SPECS:
            ttk.Label(f, text=label).pack(anchor="w")
            if key == "status":
                w = ttk.Combobox(f, values=self.STATUSES, state="readonly", width=38)
                w.set(appointment["status"] if appointment else "planned")
            elif lk:
                w = ttk.Combobox(f, values=[n for _, n in self.lk[lk]], state="readonly", width=38)
                if appointment and appointment[key]:
                    try:
                        w.current([i for i, _ in self.lk[lk]].index(appointment[key]))
                    except ValueError:
                        pass
            else:
                w = ttk.Entry(f, width=41)
                if appointment:
                    w.insert(0, str(appointment[key] or ""))
                elif key == "visit_date":
                    w.insert(0, date.today().isoformat())
                elif key == "visit_time":
                    w.insert(0, "09:00")
            w.pack(pady=(0, 6))
            self.w[key] = w
        row = ttk.Frame(f)
        row.pack(anchor="e", pady=6)
        ttk.Button(row, text="Сохранить", command=self.save).pack(side="left", padx=4)
        ttk.Button(row, text="Отмена", command=self.destroy).pack(side="left")
        self.transient(parent)
        self.grab_set()

    def save(self):
        data = {}
        for _, key, lk in self.SPECS:
            if key == "status":
                data[key] = self.w[key].get()
            elif lk:
                i = self.w[key].current()
                data[key] = self.lk[lk][i][0] if i >= 0 else None
            else:
                data[key] = self.w[key].get().strip()
        err = validate_appointment(data)
        if err:
            messagebox.showerror("Ошибка валидации", err, parent=self)
            return
        self.result = data
        self.destroy()


class PatientForm(tk.Toplevel):
    SPECS = [
        ("ФИО", "full_name", None),
        ("Дата рождения (ГГГГ-ММ-ДД)", "birth_date", None),
        ("Телефон", "phone", None),
        ("Email", "email", None),
        ("Адрес", "address", None),
        ("Заметки", "notes", None),
    ]

    def __init__(self, parent, patient=None):
        super().__init__(parent)
        self.title("Редактирование пациента" if patient else "Новый пациент")
        self.resizable(False, False)
        self.result, self.w = None, {}
        f = ttk.Frame(self, padding=14)
        f.pack()
        for label, key, _ in self.SPECS:
            ttk.Label(f, text=label).pack(anchor="w")
            w = ttk.Entry(f, width=41)
            if patient:
                w.insert(0, str(patient[key] or ""))
            w.pack(pady=(0, 6))
            self.w[key] = w
        row = ttk.Frame(f)
        row.pack(anchor="e", pady=6)
        ttk.Button(row, text="Сохранить", command=self.save).pack(side="left", padx=4)
        ttk.Button(row, text="Отмена", command=self.destroy).pack(side="left")
        self.transient(parent)
        self.grab_set()

    def save(self):
        data = {key: self.w[key].get().strip() for _, key, _ in self.SPECS}
        err = validate_patient(data)
        if err:
            messagebox.showerror("Ошибка валидации", err, parent=self)
            return
        self.result = data
        self.destroy()


class PaymentDialog(tk.Toplevel):
    def __init__(self, parent, appointment_id, total_price):
        super().__init__(parent)
        self.title("Платёж по приёму")
        self.resizable(False, False)
        self.result = None
        self.appointment_id = appointment_id
        f = ttk.Frame(self, padding=14)
        f.pack()
        ttk.Label(f, text=f"Приём №{appointment_id}. Стоимость: {total_price:.2f} ₽").pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text="Дата (ГГГГ-ММ-ДД)").pack(anchor="w")
        self.pay_date = ttk.Entry(f, width=41)
        self.pay_date.insert(0, date.today().isoformat())
        self.pay_date.pack(pady=(0, 6))
        ttk.Label(f, text="Сумма").pack(anchor="w")
        self.amount = ttk.Entry(f, width=41)
        self.amount.pack(pady=(0, 6))
        ttk.Label(f, text="Способ оплаты").pack(anchor="w")
        self.method = ttk.Combobox(f, values=("cash", "card", "transfer"), state="readonly", width=38)
        self.method.set("cash")
        self.method.pack(pady=(0, 6))
        row = ttk.Frame(f)
        row.pack(anchor="e", pady=6)
        ttk.Button(row, text="Сохранить", command=self.save).pack(side="left", padx=4)
        ttk.Button(row, text="Отмена", command=self.destroy).pack(side="left")
        self.transient(parent)
        self.grab_set()

    def save(self):
        data = {
            "appointment_id": self.appointment_id,
            "pay_date": self.pay_date.get().strip(),
            "amount": self.amount.get().strip(),
            "method": self.method.get(),
        }
        err = validate_payment(data)
        if err:
            messagebox.showerror("Ошибка валидации", err, parent=self)
            return
        self.result = data
        self.destroy()


class ReportsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Отчёты — Дентал+")
        self.geometry("820x460")
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        self.kind = ttk.Combobox(bar, values=REPORTS, state="readonly", width=24)
        self.kind.current(0)
        self.kind.pack(side="left")
        ttk.Label(bar, text="  с").pack(side="left")
        self.d1 = ttk.Entry(bar, width=11)
        self.d1.insert(0, (date.today() - timedelta(days=90)).isoformat())
        self.d1.pack(side="left", padx=4)
        ttk.Label(bar, text="по").pack(side="left")
        self.d2 = ttk.Entry(bar, width=11)
        self.d2.insert(0, date.today().isoformat())
        self.d2.pack(side="left", padx=4)
        ttk.Button(bar, text="Сформировать", command=self.run).pack(side="left", padx=8)
        self.tree = ttk.Treeview(self, show="headings")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

    def _report(self, i, d1, d2):
        with connect() as c:
            if i == 0:
                rows = c.execute(
                    "SELECT substr(visit_date,1,7) AS month, COUNT(*) AS total, "
                    "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
                    "FROM appointments GROUP BY month ORDER BY month"
                ).fetchall()
                heads = ["month", "total", "done"]
            elif i == 1:
                rows = c.execute("SELECT * FROM v_doctor_load ORDER BY revenue DESC").fetchall()
                heads = ["id", "full_name", "appointments_total", "appointments_done", "revenue"]
            elif i == 2:
                rows = c.execute(
                    "SELECT s.name, SUM(aps.qty) AS cnt, SUM(aps.qty * aps.price) AS revenue "
                    "FROM appointment_services aps "
                    "JOIN services s ON s.id = aps.service_id "
                    "JOIN appointments a ON a.id = aps.appointment_id "
                    "WHERE a.status = 'done' "
                    "GROUP BY s.id, s.name ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
                heads = ["name", "cnt", "revenue"]
            elif i == 3:
                rows = c.execute(
                    "SELECT patient, visit_date, total_price, paid, debt FROM v_debtors "
                    "WHERE debt > 0 ORDER BY debt DESC"
                ).fetchall()
                heads = ["patient", "visit_date", "total_price", "paid", "debt"]
            else:
                rows = c.execute(
                    "SELECT COALESCE(SUM(amount),0) AS revenue, COUNT(*) AS payments "
                    "FROM payments WHERE pay_date BETWEEN ? AND ?",
                    (d1.isoformat(), d2.isoformat()),
                ).fetchall()
                heads = ["revenue", "payments"]
        return heads, [tuple(r) for r in rows]

    def run(self):
        try:
            d1, d2 = date.fromisoformat(self.d1.get()), date.fromisoformat(self.d2.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Даты вводите в формате ГГГГ-ММ-ДД", parent=self)
            return
        try:
            heads, rows = self._report(self.kind.current(), d1, d2)
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", err_text(e), parent=self)
            return
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = heads
        for h in heads:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=150)
        for r in rows:
            self.tree.insert("", "end", values=r)


class MainWindow(tk.Tk):
    COLS = [
        ("id", "№", 50),
        ("visit_date", "Дата", 100),
        ("visit_time", "Время", 70),
        ("patient", "Пациент", 220),
        ("doctor", "Врач", 200),
        ("cabinet", "Каб.", 60),
        ("status", "Статус", 90),
        ("total_price", "Стоимость", 100),
    ]

    def __init__(self):
        super().__init__()
        self.title("Стоматология «Дентал+» — управление приёмами")
        self.geometry("1100x600")
        self.page, self.rows, self.rev = 0, [], {}

        role = Session.role
        can_appointment = role in ("admin", "doctor", "registrator")
        can_delete_appt = role in ("admin", "registrator")
        can_patients = role in ("admin", "doctor", "registrator")
        can_payments = role in ("admin", "accountant")

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Поиск:").pack(side="left")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.reload(reset=True))
        ttk.Entry(bar, textvariable=self.q, width=28).pack(side="left", padx=6)

        for text, cmd, ok in (
            ("Добавить приём", self.add, can_appointment),
            ("Изменить", self.edit, can_appointment),
            ("Удалить", self.delete, can_delete_appt),
            ("Пациенты", lambda: PatientsWindow(self), can_patients),
            ("Платёж", self.pay, can_payments),
            ("Отчёты", lambda: ReportsWindow(self), True),
            ("Выход", self.destroy, True),
        ):
            ttk.Button(bar, text=text, command=cmd, state="normal" if ok else "disabled").pack(side="left", padx=3)

        self.tree = ttk.Treeview(self, columns=[c for c, _, _ in self.COLS], show="headings", selectmode="browse")
        for c, t, w in self.COLS:
            self.tree.heading(c, text=t, command=lambda c=c: self.sort(c))
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6)
        self.tree.bind("<Double-1>", lambda e: self.edit())

        pager = ttk.Frame(self, padding=4)
        pager.pack()
        ttk.Button(pager, text="◀", width=3, command=lambda: self.go(-1)).pack(side="left")
        self.page_lbl = ttk.Label(pager, width=14, anchor="center")
        self.page_lbl.pack(side="left")
        ttk.Button(pager, text="▶", width=3, command=lambda: self.go(1)).pack(side="left")

        self.status = ttk.Label(self, relief="sunken", anchor="w")
        self.status.pack(fill="x")
        self.reload()

    def _search(self, text):
        sql = ("SELECT a.id, a.visit_date, a.visit_time, a.status, a.total_price, "
               "p.full_name AS patient, d.full_name AS doctor, c.number AS cabinet "
               "FROM appointments a "
               "JOIN patients p ON p.id = a.patient_id "
               "JOIN doctors  d ON d.id = a.doctor_id "
               "JOIN cabinets c ON c.id = a.cabinet_id")
        params = ()
        if text:
            like = f"%{text}%"
            sql += " WHERE p.full_name LIKE ? OR d.full_name LIKE ? OR a.visit_date LIKE ?"
            params = (like, like, like)
        sql += " ORDER BY a.visit_date DESC, a.visit_time DESC"
        with connect() as c:
            return [dict(r) for r in c.execute(sql, params)]

    def reload(self, reset=False):
        if reset:
            self.page = 0
        try:
            self.rows = self._search(self.q.get())
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", err_text(e))
            return
        self.render()

    def render(self):
        pages = max(1, -(-len(self.rows) // PAGE))
        self.page = max(0, min(self.page, pages - 1))
        self.tree.delete(*self.tree.get_children())
        for r in self.rows[self.page * PAGE:(self.page + 1) * PAGE]:
            self.tree.insert("", "end", iid=str(r["id"]),
                             values=[r[c] for c, _, _ in self.COLS])
        self.page_lbl["text"] = f"Стр. {self.page + 1} из {pages}"
        self.status["text"] = (f"Приёмов: {len(self.rows)}   |   "
                               f"{Session.name} ({Session.role})")

    def go(self, d):
        self.page += d
        self.render()

    def sort(self, col):
        self.rev[col] = not self.rev.get(col, True)
        self.rows.sort(key=lambda r: r[col], reverse=self.rev[col])
        self.render()

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите приём в таблице")
            return None
        return next(r for r in self.rows if r["id"] == int(sel[0]))

    def add(self):
        self.open_form(None)

    def edit(self):
        if (r := self.selected()):
            self.open_form(r)

    def open_form(self, appointment):
        f = AppointmentForm(self, appointment)
        self.wait_window(f)
        if not f.result:
            return
        d = f.result
        try:
            with connect() as c:
                if appointment:
                    c.execute(
                        "UPDATE appointments SET patient_id=?, doctor_id=?, cabinet_id=?, "
                        "diagnosis_id=?, visit_date=?, visit_time=?, status=?, complaint=? "
                        "WHERE id=?",
                        (d["patient_id"], d["doctor_id"], d["cabinet_id"], d["diagnosis_id"],
                         d["visit_date"], d["visit_time"], d["status"], d["complaint"], appointment["id"]),
                    )
                else:
                    c.execute(
                        "INSERT INTO appointments(patient_id, doctor_id, cabinet_id, diagnosis_id, "
                        "visit_date, visit_time, status, complaint, total_price) "
                        "VALUES(?,?,?,?,?,?,?,?,0)",
                        (d["patient_id"], d["doctor_id"], d["cabinet_id"], d["diagnosis_id"],
                         d["visit_date"], d["visit_time"], d["status"], d["complaint"]),
                    )
                c.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", err_text(e))
            return
        self.reload()

    def delete(self):
        if not (r := self.selected()):
            return
        if not messagebox.askyesno("Подтверждение", f"Удалить приём №{r['id']}?"):
            return
        try:
            with connect() as c:
                c.execute("DELETE FROM appointments WHERE id = ?", (r["id"],))
                c.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Удаление невозможно", err_text(e))
            return
        self.reload()

    def pay(self):
        r = self.selected()
        if not r:
            return
        dlg = PaymentDialog(self, r["id"], r["total_price"] or 0)
        self.wait_window(dlg)
        if not dlg.result:
            return
        d = dlg.result
        try:
            with connect() as c:
                c.execute(
                    "INSERT INTO payments(appointment_id, pay_date, amount, method) VALUES(?,?,?,?)",
                    (d["appointment_id"], d["pay_date"], float(str(d["amount"]).replace(",", ".")), d["method"]),
                )
                c.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка платежа", err_text(e))
            return
        messagebox.showinfo("Готово", "Платёж записан")
        self.reload()


class PatientsWindow(tk.Toplevel):
    COLS = [
        ("id", "№", 50),
        ("full_name", "ФИО", 260),
        ("birth_date", "Дата рождения", 120),
        ("phone", "Телефон", 140),
        ("email", "Email", 200),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Пациенты")
        self.geometry("900x500")
        self.rows = []
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Поиск:").pack(side="left")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.reload())
        ttk.Entry(bar, textvariable=self.q, width=30).pack(side="left", padx=6)
        can_edit = Session.role in ("admin", "doctor", "registrator")
        for text, cmd, ok in (
            ("Добавить", self.add, can_edit),
            ("Изменить", self.edit, can_edit),
            ("Удалить", self.delete, Session.role == "admin"),
            ("Закрыть", self.destroy, True),
        ):
            ttk.Button(bar, text=text, command=cmd, state="normal" if ok else "disabled").pack(side="left", padx=3)
        self.tree = ttk.Treeview(self, columns=[c for c, _, _ in self.COLS], show="headings", selectmode="browse")
        for c, t, w in self.COLS:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.reload()

    def reload(self):
        text = self.q.get()
        sql = "SELECT id, full_name, birth_date, phone, email FROM patients"
        params = ()
        if text:
            sql += " WHERE full_name LIKE ? OR phone LIKE ? OR email LIKE ?"
            like = f"%{text}%"
            params = (like, like, like)
        sql += " ORDER BY full_name"
        try:
            with connect() as c:
                self.rows = [dict(r) for r in c.execute(sql, params)]
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", err_text(e))
            return
        self.tree.delete(*self.tree.get_children())
        for r in self.rows:
            self.tree.insert("", "end", iid=str(r["id"]), values=[r[c] for c, _, _ in self.COLS])

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите пациента")
            return None
        return next(r for r in self.rows if r["id"] == int(sel[0]))

    def add(self):
        self.open_form(None)

    def edit(self):
        if (r := self.selected()):
            self.open_form(r)

    def open_form(self, patient):
        f = PatientForm(self, patient)
        self.wait_window(f)
        if not f.result:
            return
        d = f.result
        try:
            with connect() as c:
                if patient:
                    c.execute(
                        "UPDATE patients SET full_name=?, birth_date=?, phone=?, email=?, address=?, notes=? WHERE id=?",
                        (d["full_name"], d["birth_date"], d["phone"], d["email"], d["address"], d["notes"], patient["id"]),
                    )
                else:
                    c.execute(
                        "INSERT INTO patients(full_name, birth_date, phone, email, address, notes) "
                        "VALUES(?,?,?,?,?,?)",
                        (d["full_name"], d["birth_date"], d["phone"], d["email"], d["address"], d["notes"]),
                    )
                c.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", err_text(e))
            return
        self.reload()

    def delete(self):
        if not (r := self.selected()):
            return
        if not messagebox.askyesno("Подтверждение", f"Удалить «{r['full_name']}»?"):
            return
        try:
            with connect() as c:
                c.execute("DELETE FROM patients WHERE id = ?", (r["id"],))
                c.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Удаление невозможно", err_text(e))
            return
        self.reload()