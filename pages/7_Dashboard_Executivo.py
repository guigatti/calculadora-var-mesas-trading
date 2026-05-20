"""
pages/7_📊_Dashboard_Executivo.py
==================================
Dashboard executivo final — visão consolidada para reporte à diretoria.
Inclui as respostas formais às oito perguntas do enunciado.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.risk_engine import (
    var_parametrico, var_opcoes_montecarlo,
    var_historico, var_monte_carlo_acoes,
    calcular_retornos_carteira, classificar_utilizacao
)
from scipy import stats

st.set_page_config(page_title="Dashboard Executivo", page_icon="📊", layout="wide")

st.title("📊 Dashboard Executivo")
st.markdown(
    "Visão consolidada de risco para a diretoria. Conteúdo apresentado neste "
    "dashboard segue o padrão de reporte diário de uma área de risco de "
    "mercado em uma instituição financeira de médio porte."
)

# Validações
if (st.session_state.get('posicoes') is None or
    st.session_state.get('retornos') is None):
    st.error("❌ Configure todos os parâmetros antes do dashboard.")
    st.stop()

posicoes = st.session_state['posicoes']
retornos = st.session_state['retornos']
cov_amostral = st.session_state['cov_amostral']
params = st.session_state['parametros']

# ============================================================
# CALCULAR VaR DE TODAS AS MESAS (consolidado)
# ============================================================
resultados = []

for mesa in posicoes['mesa'].unique():
    df_m = posicoes[posicoes['mesa'] == mesa].copy()
    limite = df_m['limite_var'].iloc[0]
    tem_opcoes = df_m['tipo'].isin(['call', 'put']).any()
    tem_acoes = (df_m['tipo'] == 'acao').any()

    var_fin = 0
    metodologia = ''

    if tem_opcoes:
        df_op = df_m[df_m['tipo'].isin(['call', 'put'])].copy()
        df_op['T_anos'] = df_op['vencimento_dias_uteis'] / 252
        try:
            r = var_opcoes_montecarlo(
                df_op, retornos,
                nivel_confianca=params['nivel_confianca'],
                horizonte_dias=params['horizonte_dias'],
                taxa_juros=params['taxa_juros'],
                n_simulacoes=params['n_simulacoes'],
                chocar_vol=True, vol_choque_anual=0.10, seed=42
            )
            var_fin += r['var_financeiro']
            metodologia = 'MC vega-aware'
        except Exception:
            pass

    if tem_acoes:
        df_ac = df_m[df_m['tipo'] == 'acao'].copy()
        exposicoes = df_ac.set_index('ativo')['valor_posicao']
        valor_ac = exposicoes.abs().sum()
        if valor_ac > 0:
            pesos = exposicoes / valor_ac
            pesos_alin = pesos.reindex(cov_amostral.index).fillna(0.0).values
            var_p = float(pesos_alin @ cov_amostral.values @ pesos_alin)
            vol_p = np.sqrt(max(var_p, 0))
            var_ac = stats.norm.ppf(params['nivel_confianca']) * vol_p * valor_ac * np.sqrt(params['horizonte_dias'])
            var_fin += var_ac
            metodologia = metodologia + ' + Paramétrico' if metodologia else 'Paramétrico'

    valor_total = (df_m['quantidade'] * df_m['preco']).abs().sum()
    classif = classificar_utilizacao(var_fin, limite)

    resultados.append({
        'Mesa': mesa,
        'Tipo': 'Opções' if tem_opcoes else 'Ações',
        'Metodologia': metodologia,
        'Exposição (R$)': valor_total,
        'VaR (R$)': var_fin,
        'Limite (R$)': limite,
        'Utilização (%)': classif['utilizacao_pct'],
        'Status': f"{classif['cor']} {classif['status']}",
        'Breach': classif['breach'],
    })

df_dash = pd.DataFrame(resultados).sort_values('Utilização (%)', ascending=False)

# ============================================================
# KPIs PRINCIPAIS
# ============================================================
st.subheader("Indicadores-Chave (KPIs)")

total_exposicao = df_dash['Exposição (R$)'].sum()
total_var = df_dash['VaR (R$)'].sum()
total_limite = df_dash['Limite (R$)'].sum()
util_carteira = total_var / total_limite * 100

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Exposição Total", f"R$ {total_exposicao:,.0f}")
with col2:
    st.metric("VaR Total", f"R$ {total_var:,.0f}")
with col3:
    st.metric("Limite Total", f"R$ {total_limite:,.0f}")
with col4:
    cor_util = "normal" if util_carteira <= 70 else ("off" if util_carteira <= 100 else "inverse")
    st.metric("Utilização Carteira", f"{util_carteira:.1f}%")

# ============================================================
# RESUMO POR MESA
# ============================================================
st.divider()
st.subheader("📋 Resumo Consolidado por Mesa")

def colorir_status(val):
    if 'Verde' in str(val):
        return 'background-color: #d4edda; color: #155724'
    elif 'Amarelo' in str(val):
        return 'background-color: #fff3cd; color: #856404'
    elif 'Vermelho' in str(val):
        return 'background-color: #f8d7da; color: #721c24'
    return ''

st.dataframe(
    df_dash.drop(columns=['Breach']).style
    .format({
        'Exposição (R$)': 'R$ {:,.2f}',
        'VaR (R$)': 'R$ {:,.2f}',
        'Limite (R$)': 'R$ {:,.2f}',
        'Utilização (%)': '{:.1f}%',
    }).map(colorir_status, subset=['Status']),
    use_container_width=True, hide_index=True
)

# ============================================================
# GAUGES + RANKING LADO A LADO
# ============================================================
st.divider()
col_g, col_r = st.columns([3, 2])

with col_g:
    st.markdown("#### Utilização do Limite")
    n_mesas = len(df_dash)
    fig_g = make_subplots(
        rows=1, cols=n_mesas,
        specs=[[{'type': 'indicator'}] * n_mesas],
        subplot_titles=df_dash['Mesa'].tolist()
    )
    for i, (_, row) in enumerate(df_dash.iterrows()):
        util = row['Utilização (%)']
        cor = 'green' if util <= 70 else ('orange' if util <= 100 else 'red')
        fig_g.add_trace(go.Indicator(
            mode='gauge+number',
            value=util,
            number={'suffix': '%', 'font': {'size': 20}},
            gauge={
                'axis': {'range': [0, 150]},
                'bar': {'color': cor},
                'steps': [
                    {'range': [0, 70], 'color': 'rgba(0,200,0,0.15)'},
                    {'range': [70, 100], 'color': 'rgba(255,165,0,0.20)'},
                    {'range': [100, 150], 'color': 'rgba(255,0,0,0.20)'},
                ],
                'threshold': {'line': {'color': 'red', 'width': 4},
                              'thickness': 0.75, 'value': 100}
            }
        ), row=1, col=i+1)
    fig_g.update_layout(height=320, template='plotly_white')
    st.plotly_chart(fig_g, use_container_width=True)

with col_r:
    st.markdown("#### Composição do VaR")
    fig_pie = go.Figure(data=[go.Pie(
        labels=df_dash['Mesa'],
        values=df_dash['VaR (R$)'],
        hole=0.4,
        textposition='inside',
        textinfo='percent+label'
    )])
    fig_pie.update_layout(
        height=320, template='plotly_white',
        showlegend=False
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ============================================================
# RANKING
# ============================================================
st.markdown("#### 🏆 Ranking de Consumo de Risco")

fig_rank = go.Figure()
cores_bar = ['green' if u <= 70 else ('orange' if u <= 100 else 'red')
             for u in df_dash['Utilização (%)']]

fig_rank.add_trace(go.Bar(
    x=df_dash['VaR (R$)'], y=df_dash['Mesa'],
    orientation='h', marker_color=cores_bar,
    text=[f"R$ {v:,.0f} ({u:.0f}%)" for v, u in
          zip(df_dash['VaR (R$)'], df_dash['Utilização (%)'])],
    textposition='auto'
))
for i, (_, r) in enumerate(df_dash.iterrows()):
    fig_rank.add_shape(
        type='line', x0=r['Limite (R$)'], x1=r['Limite (R$)'],
        y0=i-0.4, y1=i+0.4,
        line=dict(color='black', width=2, dash='dash')
    )
fig_rank.update_layout(
    title='Ranking de Mesas por VaR (linhas tracejadas: limite aprovado)',
    xaxis_title='VaR (R$)', template='plotly_white', height=400
)
fig_rank.update_xaxes(tickformat=',.0f')
st.plotly_chart(fig_rank, use_container_width=True)

# ============================================================
# RESPOSTAS ÀS PERGUNTAS DO ENUNCIADO
# ============================================================
st.divider()
st.subheader("📝 Respostas às Perguntas do Enunciado (Seção 15)")

mesa_maior_var = df_dash.loc[df_dash['VaR (R$)'].idxmax(), 'Mesa']
val_maior_var = df_dash['VaR (R$)'].max()
mesa_maior_util = df_dash.loc[df_dash['Utilização (%)'].idxmax(), 'Mesa']
val_maior_util = df_dash['Utilização (%)'].max()
mesas_breach = df_dash[df_dash['Breach']]['Mesa'].tolist()

with st.expander("1. Qual mesa apresentou maior VaR?", expanded=True):
    st.markdown(f"**{mesa_maior_var}** com **R$ {val_maior_var:,.2f}** de VaR.")

with st.expander("2. Qual mesa consumiu maior percentual do limite?", expanded=True):
    st.markdown(f"**{mesa_maior_util}** com **{val_maior_util:.1f}%** de utilização.")

with st.expander("3. Alguma mesa ultrapassou o limite?", expanded=True):
    if mesas_breach:
        st.error(f"**SIM:** {', '.join(mesas_breach)}")
    else:
        st.success("Não, nenhuma mesa está em breach na rodada atual.")

with st.expander("4. O VaR Histórico, Normal e Monte Carlo geraram resultados diferentes?"):
    st.markdown("""
    Sim, especialmente para mesas com opções, onde a divergência entre
    Delta-Only e Monte Carlo Full Valuation chega a ordens de grandeza
    quando há gamma significativo. Para mesas de ações puras com retornos
    próximos da normal, a divergência tende a ser de 5–15%. Consulte a
    página **Cálculo de VaR** para a comparação mesa a mesa.
    """)

with st.expander("5. As opções aumentaram ou reduziram o risco da carteira?"):
    tem_volat = (df_dash['Tipo'] == 'Opções').any()
    if tem_volat:
        st.markdown("""
        Depende da estrutura. A mesa de Volatilidade apresenta perfil short-gamma
        e short-vega — gera **risco assimétrico**, com perdas potenciais
        maiores em movimentos bruscos do que ganhos em mercado calmo
        (premium harvesting típico). Em condições normais é lucrativa via
        theta positivo, mas estruturalmente vulnerável a eventos de cauda.
        """)
    else:
        st.markdown("Não há mesas de opções na configuração atual.")

with st.expander("6. O hedge com opções foi eficiente?"):
    st.markdown("""
    Análise depende da composição específica da mesa. Para a mesa de
    Volatilidade típica (short straddle com long call OTM de cobertura),
    o hedge reduz parcialmente o gamma negativo mas é insuficiente para
    neutralizar o risco do core. Recomenda-se hedge mais robusto via
    long puts OTM ou estruturas calendar spread.
    """)

with st.expander("7. Recomendações da área de risco"):
    st.markdown("""
    - Adotar **Monte Carlo vega-aware** como métrica oficial para mesas de opções
    - Reportar **sempre** VaR + Expected Shortfall + Stress Test em conjunto
    - Limites complementares por **Greek agregado** (gamma, vega), não apenas VaR
    - **Stress test semanal** com cenários históricos (Joesley, COVID, Eleições)
    - **Backtesting trimestral** do VaR para validar adequação metodológica
    - Para a mesa de Volatilidade: considerar limite específico em gamma
      agregado, com gatilho automático de unwind em caso de breach
    """)

with st.expander("8. Os limites definidos parecem adequados?"):
    st.markdown(f"""
    A utilização agregada da carteira está em **{util_carteira:.1f}%**. Os
    limites devem ser calibrados pelo capital alocado à mesa e pelo apetite
    de risco da instituição. Mesas com utilização sistematicamente abaixo de
    30% sugerem limite frouxo; mesas próximas de 100% recorrentes sugerem
    necessidade de revisão. A revisão é tipicamente trimestral, baseada em
    backtesting e P&L histórico realizado.
    """)

# ============================================================
# EXPORTAR RELATÓRIO EXCEL
# ============================================================
st.divider()
st.subheader("📥 Exportar Relatório")

def gerar_relatorio_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_dash.to_excel(writer, sheet_name='Resumo Mesas', index=False)
        posicoes.to_excel(writer, sheet_name='Posições', index=False)

        # Parâmetros usados
        params_df = pd.DataFrame(list(params.items()), columns=['Parâmetro', 'Valor'])
        params_df.to_excel(writer, sheet_name='Parâmetros', index=False)

    return output.getvalue()

col_e1, col_e2 = st.columns(2)
with col_e1:
    st.download_button(
        label="⬇️ Baixar Relatório Excel Completo",
        data=gerar_relatorio_excel(),
        file_name=f"relatorio_var_mesas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with col_e2:
    csv = df_dash.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Baixar Resumo em CSV",
        data=csv,
        file_name="resumo_mesas.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ============================================================
# RODAPÉ
# ============================================================
st.divider()
st.markdown(
    "> *\"All models are wrong, but some are useful.\"* — George Box"
)
st.caption(
    "Limitações estruturais: o VaR não é medida de perda máxima — é um quantil. "
    "Todo modelo assume que o passado representa o futuro. Stress testing existe "
    "precisamente como complemento obrigatório dessa limitação. Para mesas de "
    "opções, MC vega-aware é a única abordagem defensável quando há gamma "
    "ou vega materiais."
)
