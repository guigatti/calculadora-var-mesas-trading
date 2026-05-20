"""
pages/2_⚙️_Parâmetros_de_Risco.py
==================================
Configuração dos parâmetros de risco e ingestão de dados de mercado.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import baixar_precos
from utils.risk_engine import calcular_retornos, matriz_covariancia
from utils.session_init import init_session_state

st.set_page_config(page_title="Parâmetros de Risco", page_icon="⚙️", layout="wide")

# Inicializa session_state se necessário (multi-page navigation safety)
init_session_state()

st.title("⚙️ Parâmetros de Risco e Dados de Mercado")
st.markdown(
    "Configure os parâmetros que governam o cálculo do VaR e baixe os dados "
    "históricos via Yahoo Finance."
)

# Verificar se posições estão cadastradas
if st.session_state.get('posicoes') is None:
    st.error("❌ Nenhuma posição cadastrada. Vá para **Cadastro de Posições** primeiro.")
    st.stop()

# ============================================================
# PARÂMETROS DE RISCO
# ============================================================
st.subheader("Parâmetros de Cálculo")

col1, col2 = st.columns(2)

with col1:
    nivel_confianca = st.select_slider(
        "Nível de Confiança",
        options=[0.90, 0.95, 0.975, 0.99],
        value=st.session_state['parametros'].get('nivel_confianca', 0.95),
        format_func=lambda x: f"{x*100:.1f}%",
        help="95% é o padrão de mercado para VaR de gestão diária; 99% é mais conservador."
    )

    horizonte_dias = st.number_input(
        "Horizonte (dias úteis)",
        min_value=1, max_value=21,
        value=st.session_state['parametros'].get('horizonte_dias', 1),
        help="1 dia é o padrão para gestão diária; 10 dias é o padrão regulatório de Basileia."
    )

    metodologia = st.selectbox(
        "Metodologia de VaR principal",
        ['Paramétrico (Normal)', 'Histórico', 'Histórico EWMA', 'Monte Carlo'],
        index=['Paramétrico (Normal)', 'Histórico', 'Histórico EWMA', 'Monte Carlo'].index(
            st.session_state['parametros'].get('metodologia', 'Paramétrico (Normal)')
        ),
        help="A metodologia escolhida será a métrica oficial reportada no dashboard."
    )

with col2:
    lambda_ewma = st.slider(
        "λ (EWMA — RiskMetrics)",
        min_value=0.90, max_value=0.99,
        value=st.session_state['parametros'].get('lambda_ewma', 0.94),
        step=0.01,
        help="0.94 é o padrão RiskMetrics (meia-vida ~11 dias). Valores menores são mais reativos."
    )

    n_simulacoes = st.select_slider(
        "Número de Simulações (Monte Carlo)",
        options=[1000, 5000, 10_000, 25_000, 50_000, 100_000],
        value=st.session_state['parametros'].get('n_simulacoes', 10_000),
        format_func=lambda x: f"{x:,}",
        help="10.000 é o mínimo aceitável para VaR 95%; 50.000+ para VaR 99% e ES."
    )

    taxa_juros = st.number_input(
        "Taxa de Juros (Selic anualizada)",
        min_value=0.0, max_value=0.30,
        value=st.session_state['parametros'].get('taxa_juros', 0.115),
        step=0.005, format="%.4f",
        help="Usado para precificação de opções via Black-Scholes."
    )

# ============================================================
# DADOS DE MERCADO
# ============================================================
st.divider()
st.subheader("Dados Históricos de Mercado")

col_d1, col_d2 = st.columns([2, 1])
with col_d1:
    data_inicio = st.date_input(
        "Data inicial do histórico",
        value=None,
        help="Período típico: 2 anos (504 dias úteis) para amostral, 1 ano para EWMA."
    )
    if data_inicio is None:
        import datetime as _dt
        data_inicio = _dt.date.today() - _dt.timedelta(days=730)
    data_inicio_str = data_inicio.strftime("%Y-%m-%d")
    st.caption(f"📅 Início: **{data_inicio_str}** — período aproximado de 2 anos.")

with col_d2:
    st.metric("Posições", f"{len(st.session_state['posicoes'])}")
    st.metric("Mesas", f"{st.session_state['posicoes']['mesa'].nunique()}")

# ============================================================
# EXTRAIR TICKERS NECESSÁRIOS
# ============================================================
df_pos = st.session_state['posicoes']

# Tickers de ações + underlyings das opções
tickers_acoes = df_pos[df_pos['tipo'] == 'acao']['ativo'].unique().tolist()
tickers_opcoes = df_pos[df_pos['tipo'].isin(['call', 'put'])]['underlying'].dropna().unique().tolist()
tickers_unicos = list(set(tickers_acoes + tickers_opcoes))

st.markdown(f"**Tickers a baixar:** {', '.join(tickers_unicos)} ({len(tickers_unicos)} ativos)")

# ============================================================
# BOTÃO DE EXECUÇÃO
# ============================================================
if st.button("🔄 Baixar dados e calcular covariância", type="primary",
             use_container_width=True):
    with st.spinner(f"Baixando preços de {len(tickers_unicos)} ativos via Yahoo Finance..."):
        try:
            precos = baixar_precos(tuple(tickers_unicos), data_inicio_str)
            retornos = calcular_retornos(precos, tipo='log')

            # Salvar no session_state
            st.session_state['precos'] = precos
            st.session_state['retornos'] = retornos
            st.session_state['cov_amostral'] = matriz_covariancia(retornos, 'amostral')
            st.session_state['cov_ewma'] = matriz_covariancia(retornos, 'ewma', lambda_ewma)

            # Atualizar parâmetros
            st.session_state['parametros'] = {
                'nivel_confianca': nivel_confianca,
                'horizonte_dias': horizonte_dias,
                'metodologia': metodologia,
                'lambda_ewma': lambda_ewma,
                'n_simulacoes': n_simulacoes,
                'taxa_juros': taxa_juros,
                'data_inicio': data_inicio_str,
            }

            # Atualizar preços nas posições de ações
            df_pos_updated = df_pos.copy()
            for idx, row in df_pos_updated.iterrows():
                if row['tipo'] == 'acao' and row['ativo'] in precos.columns:
                    df_pos_updated.loc[idx, 'preco'] = float(precos[row['ativo']].iloc[-1])
                elif row['tipo'] in ('call', 'put') and row['underlying'] in precos.columns:
                    df_pos_updated.loc[idx, 'preco_subjacente'] = float(precos[row['underlying']].iloc[-1])
                    # Calcular preço da opção via Black-Scholes
                    from utils.risk_engine import BlackScholes
                    bs = BlackScholes(
                        S=float(precos[row['underlying']].iloc[-1]),
                        K=row['strike'],
                        T=row['vencimento_dias_uteis']/252,
                        r=taxa_juros,
                        sigma=row['vol_implicita'],
                        tipo=row['tipo']
                    )
                    df_pos_updated.loc[idx, 'preco'] = bs.preco
                    df_pos_updated.loc[idx, 'T_anos'] = row['vencimento_dias_uteis']/252

            df_pos_updated['valor_posicao'] = df_pos_updated['quantidade'] * df_pos_updated['preco']
            st.session_state['posicoes'] = df_pos_updated

            st.success(
                f"✅ Dados carregados! Período: **{precos.index[0].date()}** a "
                f"**{precos.index[-1].date()}** ({len(precos)} dias úteis)."
            )

        except Exception as e:
            st.error(f"❌ Erro ao baixar dados: {e}")
            st.info(
                "Verifique se os tickers estão no formato correto (ex: 'PETR4.SA' "
                "para ações brasileiras) e se há conexão com a internet."
            )

# ============================================================
# VISUALIZAÇÃO DOS DADOS
# ============================================================
if st.session_state.get('precos') is not None:
    st.divider()
    st.subheader("📊 Dados de Mercado Carregados")

    precos = st.session_state['precos']
    retornos = st.session_state['retornos']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Período", f"{len(precos)} dias úteis")
    with col2:
        st.metric("Tickers", f"{precos.shape[1]}")
    with col3:
        st.metric("De", f"{precos.index[0].date()}")

    # Estatísticas dos retornos
    import numpy as np
    st.markdown("#### Estatísticas dos Retornos Diários")
    desc = pd.DataFrame({
        'Vol Anual (%)': retornos.std() * np.sqrt(252) * 100,
        'Média Diária (%)': retornos.mean() * 100,
        'Skewness': retornos.skew(),
        'Kurtosis (excesso)': retornos.kurtosis(),
        'Min (%)': retornos.min() * 100,
        'Max (%)': retornos.max() * 100,
    }).round(3)
    st.dataframe(desc, use_container_width=True)

    st.caption(
        "💡 Curtose excesso > 0 indica caudas mais pesadas que a normal — "
        "evidência empírica do *fat tails* que o VaR Paramétrico subestima."
    )

    # Gráfico de preços
    import plotly.graph_objects as go
    precos_norm = precos / precos.iloc[0] * 100
    fig = go.Figure()
    for col in precos_norm.columns:
        fig.add_trace(go.Scatter(
            x=precos_norm.index, y=precos_norm[col],
            mode='lines', name=col, line=dict(width=2)
        ))
    fig.update_layout(
        title='Evolução Histórica dos Preços (Base 100)',
        xaxis_title='Data', yaxis_title='Preço Normalizado',
        template='plotly_white', height=420, hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

import pandas as pd  # Garantir import disponível
