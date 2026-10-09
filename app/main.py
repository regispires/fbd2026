from nicegui import app, ui


@app.on_connect
def start_app(): ...


def main():
    _ = ui.label("Exemplo FBD - Gestão de Eventos")

    _ = ui.run(port=8000)


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    main()
