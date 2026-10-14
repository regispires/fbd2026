from nicegui import app, ui


@app.on_connect
def start_app(): ...


def main():

    with ui.header(bordered=True, elevated=True).style(
        "display: flex; align-items: center;"
    ):
        _ = ui.label("Exemplo FBD - Gestão de Eventos").style("font-size:150%")

        _ = ui.space()
        with ui.column():
            dark_enabled = ui.dark_mode()
            _ = (
                ui.switch(text="Tema Escuro")
                .bind_value(dark_enabled)
                .props("color=accent")
            )

    with ui.page_scroller(position="bottom-right", x_offset=20, y_offset=20):
        _ = ui.button("Voltar ao topo")

    _ = ui.run(port=8000)


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    main()
