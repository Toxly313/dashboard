import dash
from dash import html, dcc
import plotly.graph_objs as go
import requests
import datetime

# Hier kommt die URL zu deinem n8n-JSON-Export
json_url = "https://deinserver.com/dashboard-summary.json"  # <-- Anpassen!

def fetch_data():
    try:
        r = requests.get(json_url)
        return r.json()
    except Exception as e:
        return {}

app = dash.Dash(__name__)
server = app.server  # WICHTIG für Hosting (z.B. auf Railway oder Heroku)

app.layout = html.Div([
    html.H1("KI Dashboard – Tägliche Geschäftsauswertung", style={"textAlign": "center"}),
    html.Div(id="summary-box", style={"fontSize": "18px", "margin": "20px"}),
    dcc.Interval(id='interval-component', interval=60*60*1000, n_intervals=0),  # Aktualisiert jede Stunde
    dcc.Graph(id='sales-chart', animate=True),
    dcc.Graph(id='product-chart', animate=True),
])

@app.callback(
    [
        dash.dependencies.Output('summary-box', 'children'),
        dash.dependencies.Output('sales-chart', 'figure'),
        dash.dependencies.Output('product-chart', 'figure')
    ],
    [dash.dependencies.Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    data = fetch_data()
    # Dummy fallback falls keine Daten:
    summary = data.get('zusammenfassung', "Noch keine Zusammenfassung verfügbar.")
    umsatztrend = data.get('umsatztrend', [100, 120, 130, 90, 150])  # Dummy
    labels = data.get('umsatztrend_labels', ['Mo', 'Di', 'Mi', 'Do', 'Fr'])  # Dummy
    produkte = data.get('meistverkaufte_produkte', {'Produkt A': 20, 'Produkt B': 30, 'Produkt C': 15})  # Dummy

    sales_fig = go.Figure(data=[
        go.Scatter(x=labels, y=umsatztrend, mode='lines+markers', line={'color': 'royalblue'})
    ])
    sales_fig.update_layout(title="Umsatztrend der letzten Tage", transition={'duration': 1000})

    product_fig = go.Figure(data=[
        go.Bar(x=list(produkte.keys()), y=list(produkte.values()), marker_color='indianred')
    ])
    product_fig.update_layout(title="Meistverkaufte Produkte", transition={'duration': 1000})

    return summary, sales_fig, product_fig

if __name__ == '__main__':
    app.run(debug=True)

app.run(debug=True, port=8050)