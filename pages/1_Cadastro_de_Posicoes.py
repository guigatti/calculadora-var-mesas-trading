"""
pages/1_📋_Cadastro_de_Posições.py
==================================
Cadastro de mesas e posições via upload Excel/CSV ou inserção manual.
Inclui download de template e validação automática.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Adicionar pasta raiz ao path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import carregar_template_posicoes, template_para_excel_bytes
from utils.session_init import init_session_state

st.set_page_config(page_title="Cadastro de Posições", page_icon="📋", layout="wide")

# Inicializa session_state se necessário (multi-page navigation safety)
init_session_state()

st.title("📋 Cadastro de Posições")
st.markdown(
    "Carregue as posições das mesas de trading via **upload de arquivo** ou "
    "**inserção manual**. Você também pode baixar o template Excel para preencher."
)

# ============================================================
# TEMPLATE DOWNLOAD
# ============================================================
with st.expander("📥 Baixar template Excel", expanded=False):
    st.markdown("""
    O template contém um exemplo completo com cinco mesas (Ações Brasil, Long & Short,
    Proprietária, Volatilidade), cobrindo ações e opções. Use-o como referência ou
    base para construir seu próprio arquivo.

    **Campos obrigatórios para todas as posições:**
    `mesa`, `ativo`, `tipo` ('acao', 'call' ou 'put'), `quantidade`, `limite_var`

    **Campos adicionais obrigatórios para opções:**
    `strike`, `vencimento_dias_uteis`, `vol_implicita`, `underlying`
    """)

    template = carregar_template_posicoes()
    template_bytes = template_para_excel_bytes(template)

    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.download_button(
            label="⬇️ Download Template Excel",
            data=template_bytes,
            file_name="template_posicoes_mesas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_b:
        st.dataframe(template, use_container_width=True, hide_index=True)

st.divider()

# ============================================================
# OPÇÕES DE ENTRADA
# ============================================================
metodo_entrada = st.radio(
    "Como você quer carregar as posições?",
    ["📤 Upload de arquivo Excel/CSV", "✏️ Inserção manual", "🎯 Usar dados do template"],
    horizontal=True,
)

st.markdown("")

# ============================================================
# MODO 1: UPLOAD
# ============================================================
if metodo_entrada == "📤 Upload de arquivo Excel/CSV":
    arquivo = st.file_uploader(
        "Faça upload do arquivo de posições",
        type=['xlsx', 'xls', 'csv'],
        help="O arquivo deve seguir o formato do template (campos obrigatórios validados)."
    )

    if arquivo is not None:
        try:
            if arquivo.name.endswith('.csv'):
                df = pd.read_csv(arquivo)
            else:
                df = pd.read_excel(arquivo, sheet_name='Posições' if 'Posições' in pd.ExcelFile(arquivo).sheet_names else 0)

            st.success(f"✅ Arquivo carregado: {len(df)} posições em {df['mesa'].nunique()} mesas.")
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("💾 Salvar posições na sessão", type="primary"):
                st.session_state['posicoes'] = df
                st.success("Posições salvas! Vá para 'Parâmetros de Risco' para continuar.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao ler arquivo: {e}")
            st.info("Verifique se o arquivo segue o formato do template.")

# ============================================================
# MODO 2: INSERÇÃO MANUAL
# ============================================================
elif metodo_entrada == "✏️ Inserção manual":
    st.markdown("Adicione posições uma a uma. Use o botão 'Adicionar' após preencher.")

    # Mostra posições já cadastradas
    if 'posicoes_manuais' not in st.session_state:
        st.session_state['posicoes_manuais'] = []

    with st.form("form_posicao", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            mesa = st.text_input("Mesa", placeholder="Ex: Ações Brasil")
            ativo = st.text_input("Ativo", placeholder="Ex: PETR4.SA")
            tipo = st.selectbox("Tipo", ['acao', 'call', 'put'])
        with col2:
            quantidade = st.number_input("Quantidade", value=0, step=1000,
                                         help="Use valor negativo para posições vendidas")
            limite_var = st.number_input("Limite de VaR (R$)", value=500_000.0,
                                          step=100_000.0, format="%.2f")
        with col3:
            st.markdown("**Apenas para opções:**")
            strike = st.number_input("Strike (K)", value=0.0, step=1.0,
                                      help="Preço de exercício")
            vencimento_dias = st.number_input("Vencimento (dias úteis)", value=30, step=1)
            vol_imp = st.number_input("Vol implícita (anualizada)", value=0.40,
                                       step=0.01, format="%.2f")
            underlying = st.text_input("Underlying", placeholder="Ex: PETR4.SA")

        submitted = st.form_submit_button("➕ Adicionar Posição", type="primary")

        if submitted:
            if not mesa or not ativo:
                st.error("Mesa e ativo são obrigatórios.")
            elif tipo in ('call', 'put') and (strike == 0 or not underlying):
                st.error("Para opções, strike e underlying são obrigatórios.")
            else:
                nova = {
                    'mesa': mesa, 'ativo': ativo, 'tipo': tipo,
                    'quantidade': quantidade, 'limite_var': limite_var,
                    'strike': strike if tipo != 'acao' else None,
                    'vencimento_dias_uteis': vencimento_dias if tipo != 'acao' else None,
                    'vol_implicita': vol_imp if tipo != 'acao' else None,
                    'underlying': underlying if tipo != 'acao' else None,
                }
                st.session_state['posicoes_manuais'].append(nova)
                st.success(f"✅ Posição adicionada: {ativo} ({tipo}) na mesa {mesa}")

    if st.session_state['posicoes_manuais']:
        df_manual = pd.DataFrame(st.session_state['posicoes_manuais'])
        st.markdown(f"### Posições cadastradas: {len(df_manual)}")
        st.dataframe(df_manual, use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("💾 Salvar posições na sessão", type="primary",
                         use_container_width=True):
                st.session_state['posicoes'] = df_manual
                st.success("Posições salvas!")
                st.rerun()
        with col_b:
            if st.button("🗑️ Limpar tudo", use_container_width=True):
                st.session_state['posicoes_manuais'] = []
                st.rerun()

# ============================================================
# MODO 3: TEMPLATE
# ============================================================
elif metodo_entrada == "🎯 Usar dados do template":
    template = carregar_template_posicoes()
    st.info(
        "📌 Carregando o template de exemplo — quatro mesas com perfil de risco "
        "distinto: Ações Brasil (long-only), Long & Short (pares casados), "
        "Proprietária (concentrada) e Volatilidade (opções com gamma negativo)."
    )
    st.dataframe(template, use_container_width=True, hide_index=True)

    if st.button("💾 Carregar template como posições", type="primary"):
        st.session_state['posicoes'] = template
        st.success("✅ Template carregado! Vá para 'Parâmetros de Risco'.")
        st.rerun()

# ============================================================
# STATUS ATUAL
# ============================================================
st.divider()
if st.session_state.get('posicoes') is not None:
    df = st.session_state['posicoes']
    st.success(
        f"✅ **{len(df)} posições** carregadas em **{df['mesa'].nunique()} mesas**. "
        "Pronto para o próximo passo: Parâmetros de Risco."
    )
    with st.expander("Visualizar posições carregadas"):
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ Nenhuma posição cadastrada ainda. Use um dos métodos acima.")
