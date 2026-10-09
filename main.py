from .gui import LoginWindow, MainWindow


def run():
    login = LoginWindow()
    login.mainloop()
    if login.ok:
        MainWindow().mainloop()


if __name__ == "__main__":
    run()