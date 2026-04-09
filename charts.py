import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from ui_theme import style_fig, PRIMARY, SECONDARY, ACCENT, SUCCESS, WARNING, DANGER

def bar_grouped(categories, before_values, after_values, labels=('Vorher', 'Nachher'), title='', h=400):
    """Erzeugt gruppiertes Balkendiagramm für Vorher‑Nachher‑Vergleich."""
    fig = go.Figure(data=[
        go.Bar(name=labels[0], x=categories, y=before_values, marker_color=PRIMARY),
        go.Bar(name=labels[1], x=categories, y=after_values, marker_color=SECONDARY)
    ])
    fig.update_layout(barmode='group')
    return style_fig(fig, title, h)

def donut_chart(value, title='', h=300):
    """Erzeugt ein Donut‑Diagramm (z. B. Belegungsgrad)."""
    rest = max(0, 100 - value)
    fig = go.Figure(data=[go.Pie(
        labels=['Belegt', 'Frei'],
        values=[value, rest],
        hole=0.65,
        marker=dict(colors=[PRIMARY, '#334155']),
        textinfo='none',
        hoverinfo='label+percent'
    )])
    fig.add_annotation(
        text=f"{value:.1f}%",
        x=0.5, y=0.5,
        font=dict(size=24, color='#F1F5F9'),
        showarrow=False
    )
    return style_fig(fig, title, h)

def tips_impact_chart(tips, h=300):
    """Visualisiert den Impact‑Score von Handlungsempfehlungen."""
    if not tips:
        return go.Figure()
    df = pd.DataFrame(tips)
    colors = [PRIMARY if score >= 8 else SECONDARY if score >= 6 else ACCENT for score in df['impact_score']]
    fig = go.Figure(data=[go.Bar(
        x=df['title'],
        y=df['impact_score'],
        marker_color=colors,
        text=df['impact_score'],
        textposition='outside'
    )])
    fig.update_layout(yaxis_title='Impact (0–10)', yaxis_range=[0, 10])
    return style_fig(fig, 'Priorität nach Impact', h)

def tips_savings_chart(tips, h=300):
    """Visualisiert die geschätzte monatliche Ersparnis."""
    if not tips:
        return go.Figure()
    df = pd.DataFrame(tips)
    fig = go.Figure(data=[go.Bar(
        x=df['title'],
        y=df['savings_eur'],
        marker_color=SUCCESS,
        text=[f"{s:.0f} €" for s in df['savings_eur']],
        textposition='outside'
    )])
    fig.update_layout(yaxis_title='Ersparnis (€ / Monat)')
    return style_fig(fig, 'Monatliche Ersparnis (Schätzung)', h)
