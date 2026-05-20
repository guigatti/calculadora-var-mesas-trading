"""
pages/6_⚡_Stress_Testing.py
============================
Aplicação de cenários históricos de stress às mesas. Cobre ações e opções
(via reprecificação Black-Scholes para opções).
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.risk_engine import (
    stress_test_acoes, stress_test_opcoes, CENARIOS_STRESS
)

st.set_page_config(page_title="Stress Testing", page_icon="⚡", layout="wide")

st.title("⚡ Stress Testing")
st.markdown(
    "Diferente do VaR (probabilístico), o stress test aplica **cenários "
    "determinísticos** — históricos ou hipotéticos — e calcula o P&L resultante. "
    "É a camada complementar obrigatória ao VaR, porque captura eventos de "
    "cauda que os modelos estatísticos subestimam por construção."
)

# Validações
if st.session_state.get('posicoes') is None:
    st.error("❌ Posições não cadastradas.")
    st.stop()

posicoes = st.session_state['posicoes']
params = st.session_state['parametros']

# ============================================================
# SELEÇÃO DE CENÁRIO
# ============================================================
col1, col2 = st.columns([2, 1])

with col1:
    cenario_nome = st.selectbox(
        "Cenário de stress",
        list(CENARIOS_STRESS.keys()) + ['Personalizado'],
        help="Cenários históricos são choques observados em eventos reais. Personalizado permite definir manualmente."
    )

with col2:
    choque_vol_pp = st.number_input(
        "Choque adicional na vol implícita (pp)",
        value=0.0, step=0.05, format="%.2f",
        help="Em Joesley Day e COVID, a vol implícita explodiu. Use +0.10 a +0.20 para replicar."
    )

# ============================================================
# CENÁRIO PERSONALIZADO
# ============================================================
if cenario_nome == 'Personalizado':
    st.subheader("Defina os choques manualmente")
    tickers_relevantes = list(set(
        list(posicoes[posicoes['tipo'] == 'acao']['ativo'].unique()) +
        list(posicoes[posicoes['tipo'].isin(['call', 'put'])]['underlying'].dropna().unique())
    ))

    cenario_choques = {}
    cols = st.columns(min(len(tickers_relevantes), 4))
    for i, ticker in enumerate(tickers_relevantes):
        with cols[i % len(cols)]:
            ch = st.number_input(
                f"{ticker} (%)",
                value=-10.0, step=1.0, format="%.1f",
                key=f"choque_{ticker}"
            )
            cenario_choques[ticker] = ch / 100
else:
    cenario_choques = CENARIOS_STRESS[cenario_nome]

# Mostrar choques aplicados
st.markdown("**Choques aplicados:**")
choques_display = pd.DataFrame([
    {'Ativo': k, 'Choque (%)': v * 100}
    for k, v in cenario_choques.items()
    if k in list(posicoes['ativo'].unique()) + list(posicoes['underlying'].dropna().unique())
])
if not choques_display.empty:
    st.dataframe(
        choques_display.style.format({'Choque (%)': '{:+.2f}%'})
        .background_gradient(subset=['Choque (%)'], cmap='RdYlGn'),
        use_container_width=True, hide_index=True
    )

st.divider()

# ============================================================
# EXECUÇÃO DO STRESS TEST
# ============================================================
st.subheader("🧪 P&L Sob o Cenário")

resultados_stress = []
detalhes_completos = []

for mesa in posicoes['mesa'].unique():
    df_m = posicoes[posicoes['mesa'] == mesa].copy()

    # Ações
    df_acoes = df_m[df_m['tipo'] == 'acao']
    pnl_acoes, det_acoes = 0, pd.DataFrame()
    if not df_acoes.empty:
        pnl_acoes, det_acoes = stress_test_acoes(df_acoes, cenario_choques)
        det_acoes['mesa'] = mesa

    # Opções
    df_opcoes = df_m[df_m['tipo'].isin(['call', 'put'])].copy()
    pnl_opcoes, det_opcoes = 0, pd.DataFrame()
    if not df_opcoes.empty:
        df_opcoes['T_anos'] = df_opcoes['vencimento_dias_uteis'] / 252
        pnl_opcoes, det_opcoes = stress_test_opcoes(
            df_opcoes, cenario_choques,
            choque_vol_pp=choque_vol_pp,
            taxa_juros=params['taxa_juros']
        )
        det_opcoes['mesa'] = mesa

    pnl_mesa = pnl_acoes + pnl_opcoes
    limite = df_m['limite_var'].iloc[0]
    resultados_stress.append({
        'Mesa': mesa,
        'P&L Ações (R$)': pnl_acoes,
        'P&L Opções (R$)': pnl_opcoes,
        'P&L Total (R$)': pnl_mesa,
        'Limite VaR (R$)': limite,
        'Múltiplo do Limite': abs(pnl_mesa) / limite if limite > 0 else 0,
    })

    if not det_acoes.empty:
        detalhes_completos.append(det_acoes)
    if not det_opcoes.empty:
        detalhes_completos.append(det_opcoes)

df_stress = pd.DataFrame(resultados_stress)

# ============================================================
# CARDS DE SUMÁRIO
# ============================================================
pnl_total_carteira = df_stress['P&L Total (R$)'].sum()
mesa_pior = df_stress.loc[df_stress['P&L Total (R$)'].idxmin(), 'Mesa']
pnl_pior = df_stress['P&L Total (R$)'].min()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        "P&L Total da Carteira",
        f"R$ {pnl_total_carteira:,.2f}",
        delta="Lucro" if pnl_total_carteira >= 0 else "Perda",
        delta_color="normal" if pnl_total_carteira >= 0 else "inverse"
    )
with col2:
    st.metric(
        f"Pior Mesa: {mesa_pior}",
        f"R$ {pnl_pior:,.2f}"
    )
with col3:
    st.metric("Cenário", cenario_nome)

# ============================================================
# TABELA DE RESULTADOS POR MESA
# ============================================================
st.markdown("**P&L por Mesa sob o Cenário:**")
st.dataframe(
    df_stress.style.format({
        'P&L Ações (R$)': 'R$ {:,.2f}',
        'P&L Opções (R$)': 'R$ {:,.2f}',
        'P&L Total (R$)': 'R$ {:,.2f}',
        'Limite VaR (R$)': 'R$ {:,.2f}',
        'Múltiplo do Limite': '{:.2f}x',
    }).background_gradient(subset=['P&L Total (R$)'], cmap='RdYlGn'),
    use_container_width=True, hide_index=True
)

# ============================================================
# VISUALIZAÇÃO
# ============================================================
fig = go.Figure()
cores = ['red' if p < 0 else 'green' for p in df_stress['P&L Total (R$)']]
fig.add_trace(go.Bar(
    x=df_stress['Mesa'],
    y=df_stress['P&L Total (R$)'],
    marker_color=cores,
    text=[f"R$ {v:,.0f}" for v in df_stress['P&L Total (R$)']],
    textposition='outside',
))
fig.update_layout(
    title=f"P&L por Mesa — {cenario_nome}",
    yaxis_title='P&L (R$)',
    template='plotly_white', height=420
)
fig.update_yaxes(tickformat=',.0f')
st.plotly_chart(fig, use_container_width=True)

# ============================================================
# COMPARAÇÃO ENTRE TODOS OS CENÁRIOS
# ============================================================
st.divider()
st.subheader("🔥 Matriz de Stress — Todos os Cenários × Todas as Mesas")

matriz_stress = []
for nome_cen, cen in CENARIOS_STRESS.items():
    row = {'Cenário': nome_cen}
    for mesa in posicoes['mesa'].unique():
        df_m = posicoes[posicoes['mesa'] == mesa].copy()
        df_acoes = df_m[df_m['tipo'] == 'acao']
        df_opcoes = df_m[df_m['tipo'].isin(['call', 'put'])].copy()

        pnl = 0
        if not df_acoes.empty:
            p_a, _ = stress_test_acoes(df_acoes, cen)
            pnl += p_a
        if not df_opcoes.empty:
            df_opcoes['T_anos'] = df_opcoes['vencimento_dias_uteis'] / 252
            p_o, _ = stress_test_opcoes(df_opcoes, cen, choque_vol_pp=0,
                                          taxa_juros=params['taxa_juros'])
            pnl += p_o
        row[mesa] = pnl
    matriz_stress.append(row)

df_matriz = pd.DataFrame(matriz_stress)

# Heatmap
mesas_cols = [c for c in df_matriz.columns if c != 'Cenário']
fig_heat = go.Figure(data=go.Heatmap(
    z=df_matriz[mesas_cols].values,
    x=mesas_cols,
    y=df_matriz['Cenário'].tolist(),
    text=[[f"R$ {v:,.0f}" for v in row] for row in df_matriz[mesas_cols].values],
    texttemplate='%{text}',
    colorscale='RdYlGn', zmid=0,
    colorbar=dict(title='P&L (R$)', tickformat=',.0f')
))
fig_heat.update_layout(
    title='Matriz de Stress Test — P&L por Mesa × Cenário',
    template='plotly_white', height=440
)
st.plotly_chart(fig_heat, use_container_width=True)

# ============================================================
# INTERPRETAÇÃO
# ============================================================
st.divider()
st.markdown("### 💡 Interpretação para o Comitê de Risco")
st.info(f"""
**Sobre os resultados do stress test:**

O P&L sob o cenário {cenario_nome} é R$ {pnl_total_carteira:,.2f} para a
carteira consolidada. Esse número deve ser comparado com:

1. **Soma dos VaRs das mesas** — perdas que excedem materialmente o VaR
   agregado revelam a inadequação do VaR como medida de eventos extremos.
   Esse não é defeito do VaR — é defeito de **interpretá-lo como perda máxima**.

2. **Capital alocado às mesas** — se o stress excede o capital alocado, o
   episódio análogo na vida real provocaria capital call ou redução forçada
   de posição (deleveraging).

3. **Apetite ao risco da instituição** — o Comitê de Risco define
   formalmente quanto a instituição está disposta a perder em eventos
   adversos. O stress test deve respeitar esse teto.

**A recomendação clássica:** reportar diariamente VaR + Expected Shortfall +
P&L de pelo menos 3 cenários de stress (histórico e hipotético).
""")
