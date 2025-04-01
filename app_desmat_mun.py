import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Output, Input, State, callback_context
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import geopandas as gpd
import io
import unidecode

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css'])
server = app.server

def load_geojson(url):
    try:
        return gpd.read_file(url)
    except Exception as e:
        print(f"Erro ao carregar {url}: {e}")
        return None

# Função para carregar CSVs com lazy loading
def load_csv(url):
    return pd.read_csv(url)

# Carregar GeoJSON
brazil_states = load_geojson('https://github.com/ScriptsRemote/Amazon/raw/main/geojson/AMZ_municipios.geojson')

# Carregar dados CSV na inicialização, sem pré-processar
df_degrad = load_csv('https://github.com/ScriptsRemote/Amazon/raw/main/csv/alertas_sad_desmatamento_08_2008_04_2024_municipios.csv')

list_states = df_degrad['ESTADO'].unique()
list_anual = sorted(df_degrad['ANO'].unique())
state_options = [{'label': state, 'value': state} for state in list_states]

app.layout = dbc.Container([
    html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H1("Análise de Desmatamento - Amazônia Legal", className="text-center mb-4"),
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
        dbc.Col(dbc.Card([
            dcc.Graph(id='bar-graph-total')
        ], className="graph-block"), width=12, lg=6),
        dbc.Col(dbc.Card([
            dcc.Graph(id='bar-graph-yearly')
        ], className="graph-block"), width=12, lg=6)
    ], className='mb-4'),
    dbc.Row([
        dbc.Col(dbc.Card([
            dcc.Graph(id='line-graph')
        ], className="graph-block"), width=12, lg=6),
        dbc.Col(dbc.Card([
            dcc.Graph(id='choropleth-map')
        ], className="graph-block"), width=12, lg=6)
    ], className='mb-4'),
    dbc.Row([
        dbc.Col(html.Label('Selecione o Ano:'), width=12),
        dbc.Col(dcc.Slider(
            id='year-slider',
            min=int(min(list_anual)),
            max=int(max(list_anual)),
            value=int(max(list_anual)),
            marks={str(year): {'label': str(year), 'style': {'transform': 'rotate(-45deg)', 'margin-top': '15px'}} for year in list_anual},
            step=None,
            tooltip={"placement": "bottom", "always_visible": True}
        ), width=12)
    ], className='mb-4'),
    dcc.Store(id='selected-states', data=[]),
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Escolha os Municípios da Amazônia Legal")),
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
        dbc.ModalHeader(dbc.ModalTitle("Escolha os Municípios da Amazônia Legal")),
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
     Output('selected-states', 'data'),
     Output('state-dropdown-modal', 'value'),
     Output('year-slider', 'value')],
    [Input('year-slider', 'value'),
     Input('choropleth-map', 'clickData'),
     Input('bar-graph-yearly', 'clickData'),
     Input('bar-graph-total', 'clickData'),
     Input('state-dropdown-modal', 'value'),
     Input('reset-button-top', 'n_clicks')],
    [State('selected-states', 'data')]
)
def update_graphs(selected_year, map_click_data, bar_click_data, total_bar_click_data, selected_state, reset_clicks, selected_states):
    triggered_id = [p['prop_id'] for p in callback_context.triggered][0]
    
    if triggered_id == 'reset-button-top.n_clicks':
        selected_states = []
        selected_state = None
        selected_year = int(max(list_anual))
    else:
        if triggered_id == 'choropleth-map.clickData' and map_click_data:
            municipio = map_click_data['points'][0]['location']
            if municipio in selected_states:
                selected_states.remove(municipio)
            else:
                selected_states.append(municipio)

        if triggered_id == 'bar-graph-yearly.clickData' and bar_click_data:
            municipio = bar_click_data['points'][0]['y']
            if municipio in selected_states:
                selected_states.remove(municipio)
            else:
                selected_states.append(municipio)

        if triggered_id == 'bar-graph-total.clickData' and total_bar_click_data:
            selected_year = total_bar_click_data['points'][0]['x']

    # Pré-processamento dos dados
    df_acumulado_ano = df_degrad.groupby(['ESTADO', 'ANO'])['AREAKM2'].sum().reset_index()
    df_acumulado_ano['AREAKM2'] = df_acumulado_ano['AREAKM2'].round(2)
    df_acumulado_ano['ANO'] = df_acumulado_ano['ANO'].astype(int)
    df_acumulado_ano['PERCENTUAL'] = df_acumulado_ano.groupby('ANO')['AREAKM2'].transform(lambda x: (x / x.sum()) * 100)
    df_acumulado_ano['PERCENTUAL'] = df_acumulado_ano['PERCENTUAL'].round(2)

    df_acumulado_ano_municipio = df_degrad.groupby(['MUNICIPIO', 'ESTADO', 'ANO'])['AREAKM2'].sum().reset_index()
    df_acumulado_ano_municipio['AREAKM2'] = df_acumulado_ano_municipio['AREAKM2'].round(2)
    df_acumulado_ano_municipio['ANO'] = df_acumulado_ano_municipio['ANO'].astype(int)
    df_acumulado_ano_municipio['PERCENTUAL'] = df_acumulado_ano_municipio.groupby('ANO')['AREAKM2'].transform(lambda x: (x / x.sum()) * 100)
    df_acumulado_ano_municipio['PERCENTUAL'] = df_acumulado_ano_municipio['PERCENTUAL'].round(2)

    if selected_state:
        df_year = df_acumulado_ano_municipio[(df_acumulado_ano_municipio['ANO'] == selected_year) & (df_acumulado_ano_municipio['ESTADO'].isin(selected_state))].sort_values(by='AREAKM2', ascending=False).head(10)
    else:
        df_year = df_acumulado_ano_municipio[df_acumulado_ano_municipio['ANO'] == selected_year].sort_values(by='AREAKM2', ascending=False).head(10)
    
    bar_yearly_fig = go.Figure(go.Bar(
        y=df_year['MUNICIPIO'],
        x=df_year['AREAKM2'],
        orientation='h',
        marker_color=['green' if municipio in selected_states else 'DarkSeaGreen' for municipio in df_year['MUNICIPIO']],
        text=[f"{value} km² ({percent}%)" for value, percent in zip(df_year['AREAKM2'], df_year['PERCENTUAL'])],
        textposition='auto'
    ))

    bar_yearly_fig.update_layout(
        xaxis_title='Área (km²)',
        yaxis_title='Município',
        bargap=0.1,
        font=dict(size=10),
        title={
        'text': f'Taxas de Desmatamentos acumulados - Municípios ({selected_year})' if not selected_state else f'Taxas de Desmatamentos acumulados - Municípios ({", ".join(selected_state)}) ({selected_year})',
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top'
        }
    )

    df_map = df_year[df_year['MUNICIPIO'].isin(selected_states)] if selected_states else df_year

    map_fig = px.choropleth_mapbox(
        df_map, geojson=brazil_states, color='AREAKM2',
        locations="MUNICIPIO", featureidkey="properties.NM_MUN",
        mapbox_style="open-street-map",
        center={"lat": -14, "lon": -55},
        color_continuous_scale='YlOrRd',  
        zoom=3
    )
    
    map_fig.update_layout(
        title={
            'text': f"Mapa de Desmatamento (km²) - {selected_year}",
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'size': 14}
        },
        margin={"r":0, "t":50, "l":0, "b":0},  # Ajuste de margem superior para incluir o título
        mapbox={
            'zoom': 3,
            'center': {"lat": -14, "lon": -55},
            'style': "open-street-map"
        }
    )

    if selected_state:
        df_line = df_acumulado_ano_municipio[df_acumulado_ano_municipio['ESTADO'].isin(selected_state)]
        line_title = f'Taxas de Desmatamento Municípios por Estado ({", ".join(selected_state)})'
    else:
        df_line = df_acumulado_ano_municipio.copy()
        line_title = 'Taxas de Desmatamento - Municípios por Estado'

    line_fig = px.line(df_line, x='ANO', y='AREAKM2', color='MUNICIPIO',
                       title=line_title, labels={'AREAKM2': 'Taxas (km²)', 'ANO': 'Ano'},
                       template='plotly_white', line_shape='spline')

    line_fig.update_traces(mode='lines+markers')

    line_fig.update_layout(
        xaxis_title='Ano',
        yaxis_title='Taxas (km²)',
        font=dict(size=10),
        yaxis=dict(tickformat=".0f"),
        legend=dict(itemsizing='constant'),
        title={
        'text': line_title,
        'x': 0.5,  # Centraliza o título horizontalmente
        'xanchor': 'center',
        'yanchor': 'top'
    }
    )

    # Acumulado total por ano com base no estado e/ou município selecionado
    if selected_state:
        df_filtered = df_degrad[df_degrad['ESTADO'].isin(selected_state)]
    else:
        df_filtered = df_degrad.copy()

    if selected_states:
        df_filtered = df_filtered[df_filtered['MUNICIPIO'].isin(selected_states)]

    df_degrad_accum_total = df_filtered.groupby('ANO')['AREAKM2'].sum().reset_index()
    df_degrad_accum_total['AREAKM2'] = df_degrad_accum_total['AREAKM2'].round(2)
    df_degrad_accum_total['ANO'] = df_degrad_accum_total['ANO'].astype(int)

    if selected_state and selected_states:
        title_text = f'Taxas de Desmatamento acumuladas - Municípios ({", ".join(selected_states)}) ({", ".join(selected_state)})'
    elif selected_state:
        title_text = f'Taxas de Desmatamento acumuladas - Municípios ({", ".join(selected_state)})'
    elif selected_states:
        title_text = f'Taxas de Desmatamento acumuladas - Municípios ({", ".join(selected_states)})'
    else:
        title_text = 'Taxas de Desmatamento acumuladas - Amazônia Legal'

    bar_total_fig = px.bar(df_degrad_accum_total, x='ANO', y='AREAKM2', text='AREAKM2', title=title_text,
                 labels={'AREAKM2': 'Taxas (km²)', 'ANO': 'Ano'}, template='plotly_white')

    bar_total_fig.update_traces(marker_color='orange', marker_line_color='orange', marker_line_width=1.5, opacity=0.6,
                      texttemplate='%{text:.2s}', textangle=-45, textposition='outside', textfont=dict(size=12, color='black', family='Arial'))

    bar_total_fig.update_layout(title={
        'text': title_text,
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top'
    },
    xaxis=dict(
        title='Ano',
        tickmode='linear',
        tickangle=-45,
        title_font=dict(size=10),  # Tamanho da fonte do título do eixo x
        tickfont=dict(size=10)     # Tamanho da fonte dos ticks do eixo x
    ),
    yaxis=dict(
        title='Taxas (km²)',
        title_font=dict(size=10),  # Tamanho da fonte do título do eixo y
        tickfont=dict(size=10)     # Tamanho da fonte dos ticks do eixo y
    ),
    font=dict(size=10),
    autosize=True  # Torna o gráfico responsivo
    )

    return bar_total_fig, bar_yearly_fig, map_fig, line_fig, selected_states, selected_state, selected_year

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

    filtered_df = df_degrad[df_degrad['ESTADO'].isin(selected_states)]
    if remove_accents:
        filtered_df = filtered_df.applymap(lambda x: unidecode.unidecode(x) if isinstance(x, str) else x)

    csv_buffer = io.StringIO()
    filtered_df.to_csv(csv_buffer, index=False, sep=decimal_separator)
    csv_buffer.seek(0)

    return dcc.send_data_frame(filtered_df.to_csv, "desmatamento_amazonia.csv", sep=decimal_separator)

if __name__ == '__main__':
    app.run(debug=False, port=8050)
