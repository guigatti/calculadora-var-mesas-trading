"""
utils/data_loader.py
====================
Funções de ingestão de dados de mercado com cache do Streamlit.

O cache (@st.cache_data) garante que o download de preços via yfinance
não seja repetido a cada interação do usuário — apenas quando os
parâmetros mudam.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


@st.cache_data(ttl=3600, show_spinner=False)
def baixar_precos(tickers: tuple, data_inicio: str, data_fim: str = None) -> pd.DataFrame:
    """
    Download de preços via yfinance com cache de 1 hora.

    IMPORTANTE: tickers deve ser tuple (não list), porque st.cache_data
    requer argumentos hasháveis.
    """
    df = yf.download(
        list(tickers),
        start=data_inicio,
        end=data_fim,
        progress=False,
        auto_adjust=True,
    )

    if df.empty:
        raise ValueError(f"Sem dados para tickers: {tickers}")

    if isinstance(df.columns, pd.MultiIndex):
        precos = df['Close']
    else:
        precos = df[['Close']].rename(columns={'Close': tickers[0]})

    return precos.dropna(how='all').ffill()


def carregar_template_posicoes() -> pd.DataFrame:
    """
    Template Excel com a estrutura esperada de posições.
    Misto ações + opções para demonstração.
    """
    template = pd.DataFrame([
        # Mesa Ações Brasil — long only
        {'mesa': 'Ações Brasil', 'ativo': 'PETR4.SA', 'tipo': 'acao',
         'quantidade': 100_000, 'limite_var': 600_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Ações Brasil', 'ativo': 'VALE3.SA', 'tipo': 'acao',
         'quantidade': 80_000, 'limite_var': 600_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Ações Brasil', 'ativo': 'ITUB4.SA', 'tipo': 'acao',
         'quantidade': 150_000, 'limite_var': 600_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Ações Brasil', 'ativo': 'BBDC4.SA', 'tipo': 'acao',
         'quantidade': 120_000, 'limite_var': 600_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Ações Brasil', 'ativo': 'ABEV3.SA', 'tipo': 'acao',
         'quantidade': 200_000, 'limite_var': 600_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},

        # Mesa Long & Short — pares
        {'mesa': 'Long & Short', 'ativo': 'ITUB4.SA', 'tipo': 'acao',
         'quantidade': 200_000, 'limite_var': 400_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Long & Short', 'ativo': 'BBDC4.SA', 'tipo': 'acao',
         'quantidade': -300_000, 'limite_var': 400_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Long & Short', 'ativo': 'PETR4.SA', 'tipo': 'acao',
         'quantidade': 150_000, 'limite_var': 400_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Long & Short', 'ativo': 'VALE3.SA', 'tipo': 'acao',
         'quantidade': -80_000, 'limite_var': 400_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},

        # Mesa Proprietária — concentrada
        {'mesa': 'Proprietária', 'ativo': 'PETR4.SA', 'tipo': 'acao',
         'quantidade': 250_000, 'limite_var': 800_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},
        {'mesa': 'Proprietária', 'ativo': 'VALE3.SA', 'tipo': 'acao',
         'quantidade': 100_000, 'limite_var': 800_000,
         'strike': None, 'vencimento_dias_uteis': None,
         'vol_implicita': None, 'underlying': None},

        # Mesa de Volatilidade — short straddle + short put + long call OTM
        {'mesa': 'Volatilidade', 'ativo': 'PETR4_C_ATM_30d', 'tipo': 'call',
         'quantidade': -100_000, 'limite_var': 500_000,
         'strike': 38.0, 'vencimento_dias_uteis': 30,
         'vol_implicita': 0.42, 'underlying': 'PETR4.SA'},
        {'mesa': 'Volatilidade', 'ativo': 'PETR4_P_ATM_30d', 'tipo': 'put',
         'quantidade': -100_000, 'limite_var': 500_000,
         'strike': 38.0, 'vencimento_dias_uteis': 30,
         'vol_implicita': 0.42, 'underlying': 'PETR4.SA'},
        {'mesa': 'Volatilidade', 'ativo': 'VALE3_C_OTM_60d', 'tipo': 'call',
         'quantidade': 50_000, 'limite_var': 500_000,
         'strike': 70.0, 'vencimento_dias_uteis': 60,
         'vol_implicita': 0.38, 'underlying': 'VALE3.SA'},
        {'mesa': 'Volatilidade', 'ativo': 'ITUB4_P_ATM_30d', 'tipo': 'put',
         'quantidade': -80_000, 'limite_var': 500_000,
         'strike': 32.0, 'vencimento_dias_uteis': 30,
         'vol_implicita': 0.32, 'underlying': 'ITUB4.SA'},
    ])
    return template


def template_para_excel_bytes(df: pd.DataFrame) -> bytes:
    """Converte o template em bytes Excel para download via Streamlit."""
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Posições')
        # Adicionar instruções em uma segunda aba
        instrucoes = pd.DataFrame({
            'Campo': ['mesa', 'ativo', 'tipo', 'quantidade', 'limite_var',
                     'strike', 'vencimento_dias_uteis', 'vol_implicita', 'underlying'],
            'Obrigatório': ['Sim', 'Sim', 'Sim', 'Sim', 'Sim',
                            'Apenas opções', 'Apenas opções',
                            'Apenas opções', 'Apenas opções'],
            'Descrição': [
                'Nome da mesa de trading',
                'Código do ativo (ex: PETR4.SA) ou identificador da opção',
                "Um de: 'acao', 'call', 'put'",
                'Quantidade (negativo = posição vendida)',
                'Limite de VaR aprovado para a mesa',
                'Preço de exercício (strike)',
                'Dias úteis até o vencimento',
                'Volatilidade implícita anualizada (ex: 0.40)',
                'Ticker do ativo subjacente (ex: PETR4.SA)',
            ]
        })
        instrucoes.to_excel(writer, index=False, sheet_name='Instruções')
    return output.getvalue()
