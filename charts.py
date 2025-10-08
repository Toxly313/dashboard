import numpy as np
import plotly.graph_objects as go
from ui_theme import style_fig, TEAL, PURPLE

def bar_grouped(x, a, b, labels=("A","B"), title=None, h=300):
    fig = go.Figure()
    fig.add_bar(name=labels[0], x=x, y=a, marker_color=TEAL)
    fig.add_bar(name=labels[1], x=x, y=b, marker_color=PURPLE)
    return style_fig(fig, title, h)

def bar_stacked(x, a, b, labels=("A","B"), title=None, h=300):
    fig = go.Figure()
    fig.add_bar(name=labels[0], x=x, y=a, marker_color=TEAL)
    fig.add_bar(name=labels[1], x=x, y=b, marker_color=PURPLE)
    fig.update_layout(barmode="stack")
    return style_fig(fig, title, h)

def line_chart(x, y1, y2=None, labels=("A","B"), title=None, h=300):
    fig = go.Figure()
    fig.add_scatter(x=x, y=y1, mode="lines+markers", name=labels[0], line=dict(width=3, color=TEAL))
    if y2 is not None:
        fig.add_scatter(x=x, y=y2, mode="lines+markers", name=labels[1], line=dict(width=3, color=PURPLE))
    return style_fig(fig, title, h)

def area_chart(x, y1, y2=None, labels=("A","B"), title=None, h=260):
    fig = go.Figure()
    fig.add_scatter(x=x, y=y1, mode="lines", fill="tozeroy", name=labels[0], line=dict(width=2, color=TEAL))
    if y2 is not None:
        fig.add_scatter(x=x, y=y2, mode="lines", fill="tozeroy", name=labels[1], line=dict(width=2, color=PURPLE, dash="dot"))
    return style_fig(fig, title, h)

def donut_chart(value, title=None, h=260):
    v = max(0, min(100, float(value or 0)))
    fig = go.Figure(go.Pie(values=[v, 100-v], labels=[f"{v:.0f}%", ""], hole=.7,
                           marker=dict(colors=[PURPLE, "#EEF2FF"]), sort=False, textinfo="label"))
    fig.update_traces(showlegend=False)
    return style_fig(fig, title, h)

def sma_forecast(y, window=3, steps=3):
    if not y: return []
    y = list(map(float, y))
    base = np.convolve(y, np.ones(window)/window, mode="valid").tolist()
    last = base[-1] if base else y[-1]
    return [last for _ in range(steps)]

def heatmap(matrix, xlabels, ylabels, title="Cohort Retention", h=300):
    fig = go.Figure(go.Heatmap(z=matrix, x=xlabels, y=ylabels, colorscale="Blues"))
    return style_fig(fig, title, h)

# --- Empfehlungen: horizontale Balken (Impact) & Ersparnis (€) ---
from ui_theme import style_fig, PURPLE, TEAL
import plotly.graph_objects as go

def tips_impact_chart(items, h=280):
    """
    items: [{'title': str, 'impact_score': int(0-10)}]
    """
    labels = [it['title'] for it in items]
    vals   = [float(it.get('impact_score', 0)) for it in items]
    fig = go.Figure(go.Bar(x=vals, y=labels, orientation='h', marker_color=PURPLE))
    fig.update_xaxes(title="Impact (0–10)", range=[0,10])
    return style_fig(fig, "Priorität nach Impact", h)

def tips_savings_chart(items, h=280):
    """
    items: [{'title': str, 'savings_eur': number}]
    """
    labels = [it['title'] for it in items]
    vals   = [float(it.get('savings_eur', 0)) for it in items]
    fig = go.Figure(go.Bar(x=vals, y=labels, orientation='h', marker_color=TEAL))
    fig.update_xaxes(title="Potenzielle Ersparnis (€ / Monat)")
    return style_fig(fig, "Monatliche Ersparnis (Schätzung)", h)

