# app/dashboards/sad_desmatamento_terras_indigenas.py
"""
Dashboard SAD – Desmatamento em Terras Indígenas (Amazônia Legal)
-----------------------------------------------------------------
Rota Flask: /sad/desmatamento_terras_indigenas/
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import List

import dash
import dash_bootstrap_components as dbc
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unidecode
from dash import Input, Output, State, callback_context, dcc, html


# ────────────────────────────────────────────────────────────────────────────
def register_sad_desmatamento_terras_indigenas(server):
    """Acopla o dashboard ao servidor Flask fornecido."""
    external_css = [
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
    ]

    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/sad/desmatamento_terras_indigenas/",
        external_stylesheets=external_css,
        suppress_callback_exceptions=True,
    )

    # ---------------------------------------------------------------- utils
    def load_geojson(url: str):
        try:
            return gpd.read_file(url)
        except Exception as e:
            print(f"Erro ao carregar {url}: {e}")
            return None

    def load_parquet(url: str):
        return pd.read_parquet(url)

    # ---------------------------------------------------------------- dados
    brazil_states = load_geojson(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/geojson/AMZ_terra_indigena.geojson"
    )

    df_desmat = load_parquet(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/csv/alertas_sad_desmatamento_08_2008_04_2024_terraIndigena.parquet"
    )

    list_states = df_desmat['ESTADO'].unique()
    list_anual = sorted(df_desmat['ANO'].unique())
    state_options = [{'label': state, 'value': state} for state in list_states]


    # Definir intervalo de análise inicial
    start_date = pd.to_datetime("2022-08-01")
    end_date = pd.to_datetime("2024-07-31")

    app.layout = dbc.Container([
        html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="fa fa-filter mr-1"), "Remover Filtros"],
                                id="reset-button-top", n_clicks=0, color="primary", className="btn-sm custom-button"
                            ), width="auto", className="d-flex justify-content-end"
                        ),
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="fa fa-map mr-1"), "Selecione o Estado"],
                                id="open-state-modal-button", className="btn btn-secondary btn-sm custom-button"
                            ), width="auto", className="d-flex justify-content-end"
                        ),
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="fa fa-map mr-1"), "Selecionar Terras Indígenas"],
                                id="open-ti-modal-button", className="btn btn-secondary btn-sm custom-button"
                            ), width="auto", className="d-flex justify-content-end"
                        ),
                        dbc.Col(
                            dbc.Button(
                                [html.I(className="fa fa-download mr-1"), "Baixar CSV"],
                                id="open-modal-button", className="btn btn-secondary btn-sm custom-button"
                            ), width="auto", className="d-flex justify-content-end"
                        )
                    ], justify="end"),
                    dcc.Download(id="download-dataframe-csv")
                ])
            ], className="mb-4 title-card"), width=12)
        ]),
        dbc.Row([
            dbc.Col(html.Label('Alterar o intervalo:'), width="auto", className="d-flex align-items-center"),
            dbc.Col(dcc.DatePickerRange(
                id='date-picker-range',
                start_date=start_date,
                end_date=end_date,
                display_format='MM/YYYY',
                className='ml-2'
            ), width="auto"),
            dbc.Col(
                dbc.Button(
                    [html.I(className="fa fa-refresh mr-1"), "Atualizar Intervalo"],
                    id="refresh-button", n_clicks=0, color="success", className="btn-sm custom-button"
                ), width="auto", className="d-flex justify-content-end ml-2"
            ),
        ], className='mb-4 align-items-center'),

        # Linha 1: Gráfico "Taxas de Desmatamento Ambiental - Todas as Terras Indígenas" e "Evolução da Desmatamento na Amazônia por Período"
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(id='bar-graph-total')
            ], className="graph-block"), width=12, lg=6),  # Gráfico "Taxas de Desmatamento Ambiental"
            dbc.Col(dbc.Card([
                dcc.Graph(id='line-graph-period')
            ], className="graph-block"), width=12, lg=6)  # Gráfico "Evolução da Desmatamento na Amazônia por Período"
        ], className='mb-4'),

        # Linha 2: Gráfico "SAD Alerta de Desmatamento  acumulados - Todas as Terras indígenas" ao lado do Mapa de Desmatamento
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(id='bar-graph-yearly')
            ], className="graph-block"), width=12, lg=6),  # Gráfico "SAD Alerta de Desmatamento  acumulados"
            dbc.Col(dbc.Card([
                dcc.Graph(id='choropleth-map')
            ], className="graph-block"), width=12, lg=6)  # Mapa de Desmatamento
        ], className='mb-4'),

        # Linha 3: Gráfico de linhas "SAD Alerta de Desmatamento  acumulados"
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(id='line-graph')
            ], className="graph-block"), width=12)  # Gráfico de linhas "SAD Alerta de Desmatamento  acumulados"
        ], className='mb-4'),

        dcc.Store(id='selected-states', data=[]),
        dcc.Store(id='selected-year', data=end_date.year),
        dcc.Store(id='selected-ti', data=[]),  # Novo store para Terras Indígenas
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Escolha Terras Indígenas da Amazônia Legal")),
            dbc.ModalBody([
                dcc.Dropdown(
                    options=state_options,
                    id="state-dropdown-modal",
                    placeholder="Selecione o Estado",
                    multi=True
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Fechar", id="close-state-modal-button", color="danger")
            ])
        ], id="state-modal", is_open=False),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Escolha as Terras Indígenas")),
            dbc.ModalBody([
                dcc.Dropdown(
                    id="ti-dropdown",
                    placeholder="Selecione as Terras Indígenas",
                    multi=True
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Fechar", id="close-ti-modal-button", color="danger")
            ])
        ], id="ti-modal", is_open=False),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Escolha as Terras Indígenas da Amazônia Legal")),
            dbc.ModalBody([
                dbc.Checklist(
                    options=state_options,
                    id="state-checklist",
                    inline=True
                ),
                html.Hr(),
                html.Div([
                    html.Label("Configurações para gerar o CSV"),
                    dbc.RadioItems(
                        options=[
                            {'label': 'Ponto', 'value': '.'},
                            {'label': 'Vírgula', 'value': ','},
                        ],
                        value='.',
                        id='decimal-separator',
                        inline=True,
                        className='mb-2'
                    ),
                    dbc.Checkbox(
                        label="Sem acentuação",
                        id="remove-accents",
                        value=False
                    )
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Download", id="download-button", className="mr-2", color="success"),
                dbc.Button("Fechar", id="close-modal-button", color="danger")
            ])
        ], id="modal", is_open=False)
    ], fluid=True)


    @app.callback(
        [Output('bar-graph-total', 'figure'),
         Output('bar-graph-yearly', 'figure'),
         Output('choropleth-map', 'figure'),
         Output('line-graph', 'figure'),
         Output('line-graph-period', 'figure'),
         Output('selected-states', 'data'),
         Output('state-dropdown-modal', 'value'),
         Output('date-picker-range', 'start_date'),
         Output('date-picker-range', 'end_date'),
         Output('selected-ti', 'data')],
        [Input('date-picker-range', 'start_date'),
         Input('date-picker-range', 'end_date'),
         Input('choropleth-map', 'clickData'),
         Input('bar-graph-yearly', 'clickData'),  # Clique no gráfico de barras verdes
         Input('bar-graph-total', 'clickData'),   # Clique no gráfico de barras laranjas
         Input('state-dropdown-modal', 'value'),
         Input('ti-dropdown', 'value'),
         Input('reset-button-top', 'n_clicks'),
         Input('refresh-button', 'n_clicks')],
        [State('selected-states', 'data'),
         State('selected-year', 'data'),
         State('selected-ti', 'data')]
    )
    def update_graphs(start_date, end_date, map_click_data, bar_click_data, total_bar_click_data, selected_state, selected_ti, reset_clicks, refresh_clicks, selected_states, selected_year, selected_ti_state):
        triggered_id = [p['prop_id'] for p in callback_context.triggered][0]

        # Reset filtros ao clicar no botão de reset
        if triggered_id == 'reset-button-top.n_clicks':
            selected_states = []
            selected_state = None
            selected_ti_state = []
            start_date = pd.to_datetime("2022-08-01")
            end_date = pd.to_datetime("2024-07-31")
            selected_year = None
        else:
            # Manipulação de cliques no gráfico de barras laranjas
            if triggered_id == 'bar-graph-total.clickData' and total_bar_click_data:
                clicked_date_str = total_bar_click_data['points'][0]['x']
                try:
                    selected_year = int(clicked_date_str[:4])
                    start_date = pd.to_datetime(f"{selected_year}-01-01")
                    end_date = pd.to_datetime(f"{selected_year}-12-31")
                except ValueError:
                    print("Erro ao converter o ano selecionado para uma data válida.")

            # Manipulação de cliques no gráfico de barras verdes
            if triggered_id == 'bar-graph-yearly.clickData' and bar_click_data:
                clicked_ti = bar_click_data['points'][0]['y']
                if clicked_ti in selected_ti_state:
                    selected_ti_state.remove(clicked_ti)
                else:
                    selected_ti_state.append(clicked_ti)

            # Manipulação de cliques no mapa para selecionar/deselecionar áreas
            if triggered_id == 'choropleth-map.clickData' and map_click_data:
                terra_indigena = map_click_data['points'][0]['location']
                if terra_indigena in selected_ti_state:
                    selected_ti_state.remove(terra_indigena)
                else:
                    selected_ti_state.append(terra_indigena)

            if selected_ti:
                selected_ti_state = selected_ti

        # Convertendo as datas de início e fim para o formato datetime do pandas
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filtrar os dados com base no intervalo de datas selecionado
        df_filtered = df_desmat[
            ((df_desmat['ANO'] == start_date.year) & (df_desmat['MES'] >= start_date.month)) |
            ((df_desmat['ANO'] > start_date.year) & (df_desmat['ANO'] < end_date.year)) |
            ((df_desmat['ANO'] == end_date.year) & (df_desmat['MES'] <= end_date.month))
        ]

        # Filtrar pelos estados e Terras Indígenas selecionados
        if selected_state:
            df_filtered = df_filtered[df_filtered['ESTADO'].isin(selected_state)]
        if selected_ti_state:
            df_filtered = df_filtered[df_filtered['TERRA_INDI'].isin(selected_ti_state)]

        # Cálculos e criação dos gráficos
        df_acumulado_ano = df_filtered.groupby(['ESTADO', 'ANO', 'MES'])['AREAKM2'].sum().reset_index()
        df_acumulado_ano['AREAKM2'] = df_acumulado_ano['AREAKM2'].round(2)
        df_acumulado_ano['PERCENTUAL'] = df_acumulado_ano.groupby(['ANO', 'MES'])['AREAKM2'].transform(lambda x: (x / x.sum()) * 100)
        df_acumulado_ano['PERCENTUAL'] = df_acumulado_ano['PERCENTUAL'].round(2)

        df_acumulado_ano_municipio = df_filtered.groupby(['TERRA_INDI', 'ESTADO', 'ANO', 'MES'])['AREAKM2'].sum().reset_index()
        df_acumulado_ano_municipio['AREAKM2'] = df_acumulado_ano_municipio['AREAKM2'].round(2)
        df_acumulado_ano_municipio['PERCENTUAL'] = df_acumulado_ano_municipio.groupby(['ANO', 'MES'])['AREAKM2'].transform(lambda x: (x / x.sum()) * 100)
        df_acumulado_ano_municipio['PERCENTUAL'] = df_acumulado_ano_municipio['PERCENTUAL'].round(2)

        ti_title = ", ".join(selected_ti_state) if selected_ti_state else "Todas as Terras Indígenas"

        if selected_state:
            df_year = df_acumulado_ano_municipio[(df_acumulado_ano_municipio['ESTADO'].isin(selected_state))].groupby(['TERRA_INDI'])['AREAKM2'].sum().reset_index().sort_values(by='AREAKM2', ascending=False).head(15)
        else:
            df_year = df_acumulado_ano_municipio.groupby(['TERRA_INDI'])['AREAKM2'].sum().reset_index().sort_values(by='AREAKM2', ascending=False).head(15)

        if selected_ti_state:
            df_year = df_year[df_year['TERRA_INDI'].isin(selected_ti_state)]

        # Ajuste aqui: usar o df_year filtrado para atualizar os valores corretamente
        bar_yearly_fig = go.Figure(go.Bar(
            y=df_year['TERRA_INDI'],
            x=df_year['AREAKM2'],
            orientation='h',
            marker_color=['green' if municipio in selected_states else 'DarkSeaGreen' for municipio in df_year['TERRA_INDI']],
            text=[f"{value:.2f} km²" for value in df_year['AREAKM2']],
            textposition='auto'
        ))

        # Inverter a ordem para que o maior valor fique no topo
        bar_yearly_fig.update_yaxes(autorange="reversed")

        bar_yearly_fig.update_layout(
            xaxis_title='Área (km²)',
            yaxis_title='Terras Indígenas',
            bargap=0.1,
            font=dict(size=10),
            title={
                'text': (
                    f'SAD Alerta de Desmatamento  acumulados - {ti_title} <br>'
                    f'({start_date.strftime("%Y-%m")} a {end_date.strftime("%Y-%m")})'
                    if not selected_state else 
                    f'SAD Alerta de Desmatamento  acumulados - {ti_title} <br>'
                    f'({" e ".join(selected_state)}) ({start_date.strftime("%Y-%m")} a {end_date.strftime("%Y-%m")})'
                ),
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            }
        )

        df_map = df_filtered.groupby('TERRA_INDI').sum(numeric_only=True).reset_index()

        map_fig = px.choropleth_mapbox(
            df_map, geojson=brazil_states, color='AREAKM2',
            locations="TERRA_INDI", featureidkey="properties.nome_uc",
            mapbox_style="open-street-map",
            center={"lat": -14, "lon": -55},
            color_continuous_scale='YlOrRd',  
            zoom=3
        )

        map_fig.update_layout(
            title={
                'text': f"Mapa de Desmatamento Ambiental (km²) - <br> {ti_title} ({start_date.strftime('%Y-%m')} a {end_date.strftime('%Y-%m')})",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'size': 14}
            },
            margin={"r":0, "t":50, "l":0, "b":0},
            mapbox={
                'zoom': 3,
                'center': {"lat": -14, "lon": -55},
                'style': "open-street-map"
            }
        )

       # Cálculo do acumulado anual
        df_line = df_filtered.groupby(['ANO', 'MES', 'TERRA_INDI', 'ESTADO'])['AREAKM2'].sum().reset_index()

        # Criar uma coluna "DATA" com o formato "ANO-MÊS"
        df_line['DATA'] = pd.to_datetime(df_line['ANO'].astype(str) + '-' + df_line['MES'].astype(str).str.zfill(2) + '-01')
        df_line = df_line.sort_values(by='DATA')

        if selected_state:
            df_line = df_line[df_line['ESTADO'].isin(selected_state)]
            line_title = f'SAD Alerta de Desmatamento acumulados - <br> {", ".join(selected_state)} ({ti_title})'
        else:
            line_title = f'SAD Alerta de Desmatamento acumulados - <br> {ti_title}'

        # Gráfico de linhas acumuladas por ano e mês
        line_fig = px.line(df_line, x='DATA', y='AREAKM2', color='TERRA_INDI',
                        title=line_title, labels={'AREAKM2': 'Área acumulada (km²)', 'DATA': 'Data'},
                        template='plotly_white', line_shape='spline', color_discrete_sequence=px.colors.sequential.Reds)

        line_fig.update_traces(mode='lines+markers')

        line_fig.update_layout(
            xaxis_title='Data (Ano-Mês)',
            yaxis_title='Área acumulada (km²)',
            font=dict(size=10),
            yaxis=dict(tickformat=".0f"),
            xaxis=dict(
                tickformat="%Y-%m",  # Formato para exibir ano e mês
                tickangle=-45  # Inclinar para melhor visualização
            ),
            legend=dict(itemsizing='constant'),
            title={
                'text': line_title,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            }
        )

        # Acumulado total por mês e ano
        df_desmat_accum_total = df_filtered.groupby(['ANO', 'MES'])['AREAKM2'].sum().reset_index()
        df_desmat_accum_total['AREAKM2'] = df_desmat_accum_total['AREAKM2'].round(2)
        df_desmat_accum_total['DATA'] = pd.to_datetime(df_desmat_accum_total[['ANO', 'MES']].astype(str).agg('-'.join, axis=1) + '-01')

        if selected_state and selected_states:
            title_text = f'SAD Alerta de Desmatamento  acumulados - <br> {ti_title} ({", ".join(selected_states)}) ({", ".join(selected_state)})'
        elif selected_state:
            title_text = f'SAD Alerta de Desmatamento  acumulados - <br> {ti_title} ({", ".join(selected_state)})'
        elif selected_states:
            title_text = f'SAD Alerta de Desmatamento  acumulados - <br> {ti_title} ({", ".join(selected_states)})'
        else:
            title_text = f'SAD Alerta de Desmatamento  acumulados - <br> {ti_title}'

        bar_total_fig = px.bar(df_desmat_accum_total, x='DATA', y='AREAKM2', text='AREAKM2', title=title_text,
                               labels={'AREAKM2': 'Área (km²)', 'DATA': 'Data'}, template='plotly_white')

        bar_total_fig.update_traces(marker_color='orange', marker_line_color='orange', marker_line_width=1.5, opacity=0.6,
                                    texttemplate='%{text:.2f}', textangle=-45, textposition='outside', textfont=dict(size=10, color='black', family='Arial'))


        # Calcular a data inicial e final
        data_inicial = df_desmat_accum_total['DATA'].min().strftime('%Y-%m')
        data_final = df_desmat_accum_total['DATA'].max().strftime('%Y-%m')

        bar_total_fig.update_layout(
            title={
                'text': title_text,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis=dict(
                title=f'Periodo de Análise {data_inicial} a {data_final}',
                tickmode='linear',
                tickangle=-45,
                title_font=dict(size=10),
                tickfont=dict(size=10),
                tickformat='%m/%Y',
                dtick="M1"
            ),
            yaxis=dict(
                title='Área (km²)',
                title_font=dict(size=10),
                tickfont=dict(size=10)
            ),
            font=dict(size=10),
            autosize=True
        )

        # Gerar múltiplos intervalos de tempo dinamicamente com base na seleção de data
        periods = []
        current_period_start = pd.to_datetime(f"{start_date.year}-08-01")

        while current_period_start < end_date:
            current_period_end = current_period_start + pd.DateOffset(years=1) - pd.DateOffset(months=1)
            label = f"Desmatamento {current_period_start.year}-{current_period_end.year}"
            periods.append({"start": current_period_start, "end": current_period_end, "label": label})
            current_period_start = current_period_start + pd.DateOffset(years=1)

        df_combined = pd.DataFrame()

        for period in periods:
            df_period = df_filtered[
                ((df_filtered['ANO'] == period["start"].year) & (df_filtered['MES'] >= period["start"].month)) |
                ((df_filtered['ANO'] == period["end"].year) & (df_filtered['MES'] <= period["end"].month))
            ]

            # Mapeamento dos números dos meses para os nomes dos meses
            meses_map = {
                1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL',
                8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'
            }

            # Agrupar os dados por ano e mês, somando as áreas
            df_grouped = df_period.groupby(['ANO', 'MES'])['AREAKM2'].sum().reset_index()
            df_grouped['Meses'] = df_grouped['MES'].map(meses_map)
            df_grouped['Período'] = period["label"]

            df_combined = pd.concat([df_combined, df_grouped])

        # Garantir a ordem dos meses no gráfico
        categoria_ordem = ['AGO', 'SET', 'OUT', 'NOV', 'DEZ', 'JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL']

        # Criando o gráfico de linha para visualização da Desmatamento
        line_fig_period = px.line(df_combined, x='Meses', y='AREAKM2', color='Período', markers=True,
                                  category_orders={"Meses": categoria_ordem},
                                  labels={'AREAKM2': 'Área (km²)', 'Meses': 'Meses'},
                                  title='Evolução da Desmatamento na Amazônia por Período')

        # Atualizando o título do gráfico de acordo com os filtros selecionados
        period_title = 'Evolução da Desmatamento na Amazônia por Período <br>'
        if selected_state:
            period_title += f' - Estados: {", ".join(selected_state)}'
        if selected_ti_state:
            period_title += f' - Terras Indígenas: {", ".join(selected_ti_state)}'

        line_fig_period.update_layout(
            xaxis_title='Meses',
            yaxis_title='Área (km²)',
            font=dict(size=10),
            legend=dict(itemsizing='constant'),
            title={
                'text': period_title,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            }
        )

        # Definir lista de cores baseadas na cor principal #007588
        color_palette = [
            '#007588',  # Cor base
            '#004c5e',  # Muito mais escuro
            '#00a6b3',  # Tom claro e mais vibrante
            '#002f3a',  # Extremamente escuro
            '#00c2d1',  # Muito mais claro e vibrante
            '#006072',  # Escuro médio
            '#80e5e5',  # Muito claro
            '#003840',  # Outro tom bem escuro
            '#33d1e0',  # Vibrante e claro
            '#001a1f',  # Quase preto
        ]

        # Aplicando cores personalizadas a cada linha
        for i, trace in enumerate(line_fig_period.data):
            trace.line.color = color_palette[i % len(color_palette)]  # Aplica a cor de forma cíclica se houver mais linhas que cores

        return bar_total_fig, bar_yearly_fig, map_fig, line_fig, line_fig_period, selected_states, selected_state, start_date, end_date, selected_ti_state

    @app.callback(
        Output("state-modal", "is_open"),
        [Input("open-state-modal-button", "n_clicks"), Input("close-state-modal-button", "n_clicks")],
        [State("state-modal", "is_open")]
    )
    def toggle_state_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("ti-modal", "is_open"),
        [Input("open-ti-modal-button", "n_clicks"), Input("close-ti-modal-button", "n_clicks")],
        [State("ti-modal", "is_open")]
    )
    def toggle_ti_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("ti-dropdown", "options"),
        [Input("state-dropdown-modal", "value")]
    )
    def update_ti_options(selected_state):
        if selected_state:
            # Filtrar o DataFrame com base no estado selecionado
            filtered_df = df_desmat[df_desmat['ESTADO'].isin(selected_state)]
            ti_options = [{'label': ti, 'value': ti} for ti in filtered_df['TERRA_INDI'].unique()]
            return ti_options
        else:
            # Se nenhum estado estiver selecionado, mostrar todas as Terras Indígenas
            ti_options = [{'label': ti, 'value': ti} for ti in df_desmat['TERRA_INDI'].unique()]
            return ti_options

    @app.callback(
        Output("modal", "is_open"),
        [Input("open-modal-button", "n_clicks"), Input("close-modal-button", "n_clicks")],
        [State("modal", "is_open")]
    )
    def toggle_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("download-dataframe-csv", "data"),
        [Input("download-button", "n_clicks")],
        [State("state-checklist", "value"), State("decimal-separator", "value"), State("remove-accents", "value")]
    )
    def download_csv(n_clicks, selected_states, decimal_separator, remove_accents):
        if n_clicks is None:
            return dash.no_update

        filtered_df = df_desmat[df_desmat['ESTADO'].isin(selected_states)]
        if remove_accents:
            filtered_df = filtered_df.applymap(lambda x: unidecode.unidecode(x) if isinstance(x, str) else x)

        csv_buffer = io.StringIO()
        filtered_df.to_csv(csv_buffer, index=False, sep=decimal_separator)
        csv_buffer.seek(0)

        return dcc.send_data_frame(filtered_df.to_csv, "degradacao_amazonia.csv", sep=decimal_separator)

    return app