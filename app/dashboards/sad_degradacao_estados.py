# app/dashboards/sad_degradacao_estados.py
"""
Dashboard SAD – Degradação por Estados (Amazônia Legal)
-------------------------------------------------------
Rota Flask: /sad/degradacao_estados/
"""

from __future__ import annotations

import io
from typing import List

import dash
import dash_bootstrap_components as dbc
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unidecode
from dash import Input, Output, State, callback_context, dcc, html


# ──────────────────────────────────────────────────────────────────────────────
# Função de registro – chame-a no seu create_app()
# ──────────────────────────────────────────────────────────────────────────────
def register_sad_degradacao_estados(server):
    external_css = [
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
    ]

    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/sad/degradacao_estados/",
        external_stylesheets=external_css,
        suppress_callback_exceptions=True,
    )

    # ------------------------------------------------------------------ utils
    def load_geojson(url: str):
        try:
            return gpd.read_file(url)
        except Exception as e:
            print(f"Erro ao carregar {url}: {e}")
            return None

    # ------------------------------------------------------------------ dados
    brazil_states = load_geojson(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/geojson/AMZ_estados.geojson"
    )

    df_degrad = pd.read_parquet(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/csv/alertas_sad_degradacao_09_2008_04_2024_municipio.parquet"
    )

    df_acumulado_ano = (
        df_degrad.groupby(["ESTADO", "ANO"])["AREAKM2"].sum().reset_index()
    )
    df_acumulado_ano["AREAKM2"] = df_acumulado_ano["AREAKM2"].round(2)
    df_acumulado_ano["ANO"] = df_acumulado_ano["ANO"].astype(int)
    df_acumulado_ano["PERCENTUAL"] = df_acumulado_ano.groupby("ANO")[
        "AREAKM2"
    ].transform(lambda x: (x / x.sum()) * 100)
    df_acumulado_ano["PERCENTUAL"] = df_acumulado_ano["PERCENTUAL"].round(2)

    list_states = df_degrad.ESTADO.unique()
    list_anual: List[int] = sorted(df_degrad.ANO.unique())
    state_options = [{"label": s, "value": s} for s in list_states]

    # ------------------------------------------------------------------ layout
    app.layout = dbc.Container(
        [
            html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
            # ---- título + botões -----------------------------------------
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H1(
                                    "Análise de Degradação - Amazônia Legal",
                                    className="text-center mb-4",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-filter mr-1"),
                                                    "Remover Filtros",
                                                ],
                                                id="reset-button-top",
                                                n_clicks=0,
                                                color="primary",
                                                className="btn-sm custom-button",
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-download mr-1"),
                                                    "Baixar CSV",
                                                ],
                                                id="open-modal-button",
                                                className="btn btn-secondary btn-sm custom-button",
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end",
                                        ),
                                    ],
                                    justify="end",
                                ),
                                dcc.Download(id="download-dataframe-csv"),
                            ]
                        ),
                        className="mb-4 title-card",
                    ),
                    width=12,
                )
            ),
            # ---- blocos de gráficos ---------------------------------------
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-total"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-yearly"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                ],
                className="mb-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="line-graph"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="choropleth-map"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                ],
                className="mb-4",
            ),
            # ---- slider de ano --------------------------------------------
            dbc.Row(
                [
                    dbc.Col(html.Label("Selecione o Ano:"), width=12),
                    dbc.Col(
                        dcc.Slider(
                            id="year-slider",
                            min=int(min(list_anual)),
                            max=int(max(list_anual)),
                            value=int(max(list_anual)),
                            marks={
                                str(y): {
                                    "label": str(y),
                                    "style": {
                                        "transform": "rotate(-45deg)",
                                        "margin-top": "15px",
                                    },
                                }
                                for y in list_anual
                            },
                            step=None,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                        width=12,
                    ),
                ],
                className="mb-4",
            ),
            dcc.Store(id="selected-states", data=[]),
            # ---- modal de download ----------------------------------------
            dbc.Modal(
                [
                    dbc.ModalHeader(
                        dbc.ModalTitle("Escolha os estados da Amazônia Legal")
                    ),
                    dbc.ModalBody(
                        [
                            dbc.Checklist(
                                options=state_options,
                                id="state-checklist",
                                inline=True,
                            ),
                            html.Hr(),
                            html.Div(
                                [
                                    html.Label("Configurações para gerar o CSV"),
                                    dbc.RadioItems(
                                        options=[
                                            {"label": "Ponto", "value": "."},
                                            {"label": "Vírgula", "value": ","},
                                        ],
                                        value=".",
                                        id="decimal-separator",
                                        inline=True,
                                        className="mb-2",
                                    ),
                                    dbc.Checkbox(
                                        label="Sem acentuação",
                                        id="remove-accents",
                                    ),
                                ]
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button(
                                "Download",
                                id="download-button",
                                className="mr-2",
                                color="success",
                            ),
                            dbc.Button("Fechar", id="close-modal-button", color="danger"),
                        ]
                    ),
                ],
                id="modal",
                is_open=False,
            ),
        ],
        fluid=True,
    )

    # ------------------------------------------------------------------ callbacks
    @app.callback(Output("bar-graph-total", "figure"), Input("bar-graph-total", "id"))
    def update_bar_total(_):
        df_degrad_accum_total = (
            df_degrad.groupby("ANO")["AREAKM2"].sum().reset_index()
        )
        df_degrad_accum_total["AREAKM2"] = df_degrad_accum_total["AREAKM2"].round(2)
        df_degrad_accum_total["ANO"] = df_degrad_accum_total["ANO"].astype(int)

        fig = px.bar(
            df_degrad_accum_total,
            x="ANO",
            y="AREAKM2",
            text="AREAKM2",
            title="Taxas de degradação<br>Amazônia Legal - Estados",
            labels={"AREAKM2": "Área (km²)", "ANO": "Ano"},
            template="plotly_white",
        )
        fig.update_traces(
            marker_color="orange",
            marker_line_color="orange",
            marker_line_width=1.5,
            opacity=0.6,
            texttemplate="%{text:.2s}",
            textangle=-45,
            textposition="outside",
            textfont=dict(size=12, color="black", family="Arial"),
        )
        fig.update_layout(
            title=dict(
                text="SAD Alerta de Degradação Florestal<br>Amazônia Legal - Estados",
                x=0.5,
            ),
            xaxis=dict(
                title="Período Analisado",
                tickmode="linear",
                tickangle=-45,
                title_font=dict(size=10),
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                title="Degradação Florestal(km²)",
                title_font=dict(size=10),
                tickfont=dict(size=10),
            ),
            font=dict(size=10),
            autosize=True,
        )
        return fig

    @app.callback(
        [
            Output("bar-graph-yearly", "figure"),
            Output("choropleth-map", "figure"),
            Output("line-graph", "figure"),
            Output("selected-states", "data"),
        ],
        [
            Input("year-slider", "value"),
            Input("choropleth-map", "clickData"),
            Input("bar-graph-yearly", "clickData"),
            Input("bar-graph-total", "clickData"),
            Input("reset-button-top", "n_clicks"),
        ],
        [State("selected-states", "data")],
    )
    def update_graphs(
        selected_year,
        map_click_data,
        bar_click_data,
        total_bar_click_data,
        reset_clicks,
        selected_states,
    ):
        triggered_id = [p["prop_id"] for p in callback_context.triggered][0]

        if triggered_id == "reset-button-top.n_clicks":
            selected_states = []
        else:
            if triggered_id == "choropleth-map.clickData" and map_click_data:
                state = map_click_data["points"][0]["location"]
                selected_states = (
                    [s for s in selected_states if s != state]
                    if state in selected_states
                    else selected_states + [state]
                )

            if triggered_id == "bar-graph-yearly.clickData" and bar_click_data:
                state = bar_click_data["points"][0]["y"]
                selected_states = (
                    [s for s in selected_states if s != state]
                    if state in selected_states
                    else selected_states + [state]
                )

            if triggered_id == "bar-graph-total.clickData" and total_bar_click_data:
                selected_year = total_bar_click_data["points"][0]["x"]

        # -------- barras horizontais ano --------------------------------
        df_year = (
            df_acumulado_ano[df_acumulado_ano["ANO"] == selected_year]
            .sort_values(by="AREAKM2", ascending=True)
            .copy()
        )
        bar_fig = go.Figure(
            go.Bar(
                y=df_year["ESTADO"],
                x=df_year["AREAKM2"],
                orientation="h",
                marker_color=[
                    "green" if s in selected_states else "DarkSeaGreen"
                    for s in df_year["ESTADO"]
                ],
                text=[
                    f"{v} km² ({p}%)"
                    for v, p in zip(df_year["AREAKM2"], df_year["PERCENTUAL"])
                ],
                textposition="auto",
            )
        )
        bar_fig.update_layout(
            xaxis_title="Área (km²)",
            yaxis_title="Estado",
            bargap=0.1,
            font=dict(size=10),
            title=dict(
                text=f"SAD Alertas de Degradação Florestal Acumulado - Estados ({selected_year})",
                x=0.5,
            ),
        )

        # -------- mapa ---------------------------------------------------
        df_map = df_year[df_year["ESTADO"].isin(selected_states)] if selected_states else df_year
        map_fig = px.choropleth_mapbox(
            df_map,
            geojson=brazil_states,
            color="AREAKM2",
            locations="ESTADO",
            featureidkey="properties.Estado",
            mapbox_style="open-street-map",
            center={"lat": -14, "lon": -55},
            color_continuous_scale="YlOrRd",
            zoom=3,
        )
        map_fig.update_layout(
            title=dict(
                text=f"Mapa de Degradação Ambiental (km²) - {selected_year}",
                x=0.5,
                font={"size": 14},
            ),
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            mapbox={"zoom": 3, "center": {"lat": -14, "lon": -55}},
        )

        # -------- linha temporal ----------------------------------------
        df_line = (
            df_acumulado_ano[df_acumulado_ano["ESTADO"].isin(selected_states)]
            if selected_states
            else df_acumulado_ano.copy()
        )
        line_title = (
            "SAD Alertas de Degradação Florestal - Estados Selecionados"
            if selected_states
            else "SAD Alertas de Degradação Florestal - Amazônia Legal - Estados"
        )
        line_fig = px.line(
            df_line,
            x="ANO",
            y="AREAKM2",
            color="ESTADO",
            title=line_title,
            labels={
                "AREAKM2": "SAD Alertas de Degradação Florestal(km²)",
                "ANO": "Ano",
            },
            template="plotly_white",
            line_shape="spline",
            color_discrete_sequence=px.colors.sequential.Reds,
        )
        line_fig.update_traces(mode="lines+markers")
        line_fig.update_layout(
            xaxis_title="Ano",
            yaxis_title="SAD Alertas de Degradação Florestal(km²)",
            font=dict(size=10),
            yaxis=dict(tickformat=".0f"),
            legend=dict(itemsizing="constant"),
            title=dict(text=line_title, x=0.5),
        )

        return bar_fig, map_fig, line_fig, selected_states

    # --------------- modais + download -----------------------------------
    @app.callback(
        Output("year-slider", "value"), Input("bar-graph-total", "clickData")
    )
    def update_year_slider(click_data):
        if click_data:
            selected_year = click_data["points"][0]["x"]
            if isinstance(selected_year, int):
                return selected_year
        return dash.no_update

    @app.callback(
        Output("modal", "is_open"),
        [Input("open-modal-button", "n_clicks"), Input("close-modal-button", "n_clicks")],
        [State("modal", "is_open")],
    )
    def toggle_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("download-dataframe-csv", "data"),
        [Input("download-button", "n_clicks")],
        [
            State("state-checklist", "value"),
            State("decimal-separator", "value"),
            State("remove-accents", "value"),
        ],
    )
    def download_csv(n_clicks, selected_states, decimal_separator, remove_accents):
        if n_clicks is None:
            return dash.no_update

        filtered_df = df_degrad[df_degrad["ESTADO"].isin(selected_states)]
        if remove_accents:
            filtered_df = filtered_df.applymap(
                lambda x: unidecode.unidecode(x) if isinstance(x, str) else x
            )

        return dcc.send_data_frame(
            filtered_df.to_csv,
            "degradacao_amazonia.csv",
            sep=decimal_separator,
            index=False,
        )

    # Quem sobe é o Flask “pai”; não chamamos app.run() aqui
    return app
