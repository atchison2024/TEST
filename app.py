
import dash
from dash import html, dcc, Input, Output, State
import numpy as np
import plotly.graph_objs as go

app = dash.Dash(__name__)
server = app.server  # for deployment

NUM_ASSETS = 5

def generate_inputs(label, input_id):
    return html.Div([
        html.Label(f"{label} for Asset {i+1}:"),
        dcc.Input(id=f"{input_id}_{i}", type="number", step=0.01, required=True)
        for i in range(NUM_ASSETS)
    ])

app.layout = html.Div([
    html.H2("Efficient Frontier Calculator for 5 Assets"),
    html.Div(generate_inputs("Expected Return (%)", "return")),
    html.Br(),
    html.Div(generate_inputs("Volatility (%)", "vol")),
    html.Br(),
    html.Div(generate_inputs("Weight (%)", "weight")),
    html.Br(),
    html.Button("Run", id="run-button", n_clicks=0),
    dcc.Graph(id="frontier-graph"),
])

@app.callback(
    Output("frontier-graph", "figure"),
    Input("run-button", "n_clicks"),
    [State(f"return_{i}", "value") for i in range(NUM_ASSETS)] +
    [State(f"vol_{i}", "value") for i in range(NUM_ASSETS)] +
    [State(f"weight_{i}", "value") for i in range(NUM_ASSETS)]
)
def update_graph(n_clicks, *inputs):
    if n_clicks == 0:
        return go.Figure()

    returns = np.array(inputs[:NUM_ASSETS]) / 100
    vols = np.array(inputs[NUM_ASSETS:2*NUM_ASSETS]) / 100
    weights = np.array(inputs[2*NUM_ASSETS:]) / 100
    weights /= weights.sum()

    # Random correlation matrix
    corr = np.eye(NUM_ASSETS)
    for i in range(NUM_ASSETS):
        for j in range(i+1, NUM_ASSETS):
            r = np.random.uniform(0.2, 0.8)
            corr[i, j] = corr[j, i] = r

    cov_matrix = np.outer(vols, vols) * corr

    # Generate portfolios
    n_portfolios = 5000
    results = np.zeros((3, n_portfolios))
    for i in range(n_portfolios):
        w = np.random.dirichlet(np.ones(NUM_ASSETS))
        port_return = np.sum(w * returns)
        port_vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
        sharpe = port_return / port_vol
        results[:, i] = [port_vol, port_return, sharpe]

    fig = go.Figure(
        data=go.Scatter(
            x=results[0, :], y=results[1, :],
            mode='markers',
            marker=dict(color=results[2, :], colorscale='Viridis', showscale=True),
            name='Portfolios'
        )
    )

    # Add user's custom portfolio
    user_return = np.sum(weights * returns)
    user_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    fig.add_trace(go.Scatter(
        x=[user_vol], y=[user_return],
        mode='markers+text',
        marker=dict(color='red', size=10),
        text=["Your Portfolio"],
        name="Your Portfolio"
    ))

    fig.update_layout(title="Efficient Frontier",
                      xaxis_title="Volatility (Std Dev)",
                      yaxis_title="Expected Return",
                      template="plotly_white")

    return fig

if __name__ == "__main__":
    app.run_server(debug=True)
