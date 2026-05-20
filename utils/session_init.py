"""
utils/session_init.py
=====================
Inicialização centralizada do st.session_state.

O Streamlit multi-página carrega páginas individuais sem garantir que o
app.py raiz tenha sido executado primeiro. Por isso cada página precisa
chamar init_session_state() no início para garantir que todas as chaves
default existam, evitando KeyError.
"""
import streamlit as st


def init_session_state():
    """Inicializa todas as chaves do session_state com valores default."""
    defaults = {
        'posicoes': None,
        'precos': None,
        'retornos': None,
        'cov_amostral': None,
        'cov_ewma': None,
        'parametros': {
            'nivel_confianca': 0.95,
            'horizonte_dias': 1,
            'metodologia': 'Paramétrico (Normal)',
            'lambda_ewma': 0.94,
            'n_simulacoes': 10_000,
            'taxa_juros': 0.115,
            'data_inicio': '2023-01-01',
        },
        'resultados_var': {},
        'resultados_opcoes': {},
        'posicoes_manuais': [],
        'dashboard_resumo': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
