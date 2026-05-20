"""
utils/risk_engine.py
====================
Motor de cálculo de risco — reaproveita toda a lógica desenvolvida nos
notebooks Colab das Fases 1 e 2, organizada em funções modulares para
consumo pelas páginas do Streamlit.

Inclui:
- Black-Scholes-Merton e Greeks analíticos
- VaR Histórico (simples e EWMA)
- VaR Paramétrico (Normal) com Component VaR
- VaR Monte Carlo via GBM correlacionado
- Quatro abordagens de VaR para opções
- Expected Shortfall (todas as variantes)
- Stress testing determinístico
"""
import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime, timedelta
from typing import Optional, Sequence, Dict


# ============================================================
# DADOS DE MERCADO
# ============================================================
def calcular_retornos(precos: pd.DataFrame, tipo: str = 'log') -> pd.DataFrame:
    """Calcula retornos a partir da série de preços."""
    if tipo == 'log':
        return np.log(precos / precos.shift(1)).dropna(how='all')
    return precos.pct_change().dropna(how='all')


def matriz_covariancia(retornos: pd.DataFrame, metodo: str = 'amostral',
                       lambda_ewma: float = 0.94) -> pd.DataFrame:
    """Estima matriz de covariância amostral ou EWMA."""
    if metodo == 'amostral':
        return retornos.cov()
    if metodo == 'ewma':
        arr = retornos.dropna().values
        n_obs, n = arr.shape
        cov = np.cov(arr[:30].T, ddof=1)
        for t in range(30, n_obs):
            r = arr[t].reshape(-1, 1)
            cov = lambda_ewma * cov + (1 - lambda_ewma) * (r @ r.T)
        return pd.DataFrame(cov, index=retornos.columns, columns=retornos.columns)
    raise ValueError(f"Método inválido: {metodo}")


# ============================================================
# BLACK-SCHOLES E GREEKS
# ============================================================
class BlackScholes:
    """Pricing Black-Scholes-Merton e Greeks analíticos para opções europeias."""

    def __init__(self, S, K, T, r, sigma, q=0.0, tipo='call'):
        self.S, self.K, self.T = S, K, T
        self.r, self.sigma, self.q = r, sigma, q
        self.tipo = tipo.lower()
        if T <= 0:
            self._vencida = True
        else:
            self._vencida = False
            self.d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            self.d2 = self.d1 - sigma*np.sqrt(T)

    @property
    def preco(self):
        if self._vencida:
            return max(self.S - self.K, 0) if self.tipo == 'call' else max(self.K - self.S, 0)
        N = stats.norm.cdf
        if self.tipo == 'call':
            return self.S*np.exp(-self.q*self.T)*N(self.d1) - self.K*np.exp(-self.r*self.T)*N(self.d2)
        return self.K*np.exp(-self.r*self.T)*N(-self.d2) - self.S*np.exp(-self.q*self.T)*N(-self.d1)

    @property
    def delta(self):
        if self._vencida:
            if self.tipo == 'call':
                return 1.0 if self.S > self.K else 0.0
            return -1.0 if self.S < self.K else 0.0
        N = stats.norm.cdf
        if self.tipo == 'call':
            return np.exp(-self.q*self.T) * N(self.d1)
        return -np.exp(-self.q*self.T) * N(-self.d1)

    @property
    def gamma(self):
        if self._vencida:
            return 0.0
        return np.exp(-self.q*self.T) * stats.norm.pdf(self.d1) / (self.S*self.sigma*np.sqrt(self.T))

    @property
    def vega(self):
        if self._vencida:
            return 0.0
        return self.S * np.exp(-self.q*self.T) * stats.norm.pdf(self.d1) * np.sqrt(self.T) / 100

    @property
    def theta(self):
        if self._vencida:
            return 0.0
        n, N = stats.norm.pdf, stats.norm.cdf
        common = -(self.S*np.exp(-self.q*self.T)*n(self.d1)*self.sigma / (2*np.sqrt(self.T)))
        if self.tipo == 'call':
            theta_ano = (common - self.r*self.K*np.exp(-self.r*self.T)*N(self.d2)
                         + self.q*self.S*np.exp(-self.q*self.T)*N(self.d1))
        else:
            theta_ano = (common + self.r*self.K*np.exp(-self.r*self.T)*N(-self.d2)
                         - self.q*self.S*np.exp(-self.q*self.T)*N(-self.d1))
        return theta_ano / 365

    @property
    def rho(self):
        if self._vencida:
            return 0.0
        N = stats.norm.cdf
        if self.tipo == 'call':
            return self.K*self.T*np.exp(-self.r*self.T)*N(self.d2) / 100
        return -self.K*self.T*np.exp(-self.r*self.T)*N(-self.d2) / 100

    def greeks(self):
        return {'preco': self.preco, 'delta': self.delta, 'gamma': self.gamma,
                'vega': self.vega, 'theta': self.theta, 'rho': self.rho}


# ============================================================
# VaR HISTÓRICO
# ============================================================
def calcular_retornos_carteira(retornos_ativos: pd.DataFrame,
                                pesos: pd.Series) -> pd.Series:
    """Calcula retornos da carteira ponderados pelos pesos."""
    pesos_alinhados = pesos.reindex(retornos_ativos.columns).fillna(0)
    return retornos_ativos @ pesos_alinhados


def var_historico(retornos_carteira, valor_carteira,
                  nivel_confianca=0.95, horizonte_dias=1):
    """VaR Histórico simples."""
    alpha = 1 - nivel_confianca
    percentil = np.percentile(retornos_carteira.dropna(), alpha * 100)
    fator_h = np.sqrt(horizonte_dias)
    var_pct = -percentil * fator_h
    return {
        'metodologia': 'Histórico',
        'var_pct': var_pct,
        'var_financeiro': var_pct * valor_carteira,
        'percentil_retorno': percentil,
        'nivel_confianca': nivel_confianca,
        'horizonte_dias': horizonte_dias,
        'n_observacoes': len(retornos_carteira.dropna()),
    }


def var_historico_ewma(retornos_carteira, valor_carteira,
                       nivel_confianca=0.95, lambda_decay=0.97, horizonte_dias=1):
    """VaR Histórico com ponderação exponencial."""
    ret = retornos_carteira.dropna()
    n = len(ret)
    alpha = 1 - nivel_confianca
    pesos = (1 - lambda_decay) * lambda_decay ** np.arange(n - 1, -1, -1)
    pesos = pesos / pesos.sum()
    df = pd.DataFrame({'retorno': ret.values, 'peso': pesos}).sort_values('retorno')
    df['peso_acum'] = df['peso'].cumsum()
    percentil = df[df['peso_acum'] >= alpha].iloc[0]['retorno']
    fator_h = np.sqrt(horizonte_dias)
    var_pct = -percentil * fator_h
    return {
        'metodologia': 'Histórico EWMA',
        'var_pct': var_pct,
        'var_financeiro': var_pct * valor_carteira,
        'lambda_decay': lambda_decay,
        'nivel_confianca': nivel_confianca,
    }


def expected_shortfall_historico(retornos_carteira, valor_carteira,
                                 nivel_confianca=0.975, horizonte_dias=1):
    """Expected Shortfall histórico — média da cauda."""
    ret = retornos_carteira.dropna()
    alpha = 1 - nivel_confianca
    percentil = np.percentile(ret, alpha * 100)
    cauda = ret[ret <= percentil]
    es_pct = -cauda.mean() * np.sqrt(horizonte_dias)
    return {
        'metodologia': 'ES Histórico',
        'es_pct': es_pct,
        'es_financeiro': es_pct * valor_carteira,
        'nivel_confianca': nivel_confianca,
    }


# ============================================================
# VaR PARAMÉTRICO
# ============================================================
def var_parametrico(pesos, cov_matrix, valor_carteira,
                    nivel_confianca=0.95, horizonte_dias=1):
    """VaR Paramétrico (Normal) via w'Σw."""
    pesos_alinhados = pesos.reindex(cov_matrix.index).fillna(0.0)
    w = pesos_alinhados.values
    var_carteira = float(w @ cov_matrix.values @ w)
    vol_diaria = np.sqrt(max(var_carteira, 0.0))
    vol_h = vol_diaria * np.sqrt(horizonte_dias)
    z_alpha = stats.norm.ppf(nivel_confianca)
    var_pct = z_alpha * vol_h
    return {
        'metodologia': 'Paramétrico (Normal)',
        'var_pct': var_pct,
        'var_financeiro': var_pct * valor_carteira,
        'volatilidade_diaria': vol_diaria,
        'z_alpha': z_alpha,
        'nivel_confianca': nivel_confianca,
    }


def component_var(pesos, cov_matrix, valor_carteira,
                  nivel_confianca=0.95, horizonte_dias=1):
    """Decomposição do VaR em contribuições por ativo."""
    pesos_alinhados = pesos.reindex(cov_matrix.index).fillna(0.0)
    w = pesos_alinhados.values
    sigma_w = cov_matrix.values @ w
    var_p = float(w @ sigma_w)
    vol_p = np.sqrt(max(var_p, 0.0))
    if vol_p < 1e-10:
        return pd.DataFrame()
    z_alpha = stats.norm.ppf(nivel_confianca)
    fator_h = np.sqrt(horizonte_dias)
    marginal_var_pct = (sigma_w / vol_p) * z_alpha * fator_h
    component_var_pct = w * marginal_var_pct
    df = pd.DataFrame({
        'ativo': cov_matrix.index,
        'peso': w,
        'marginal_var_pct': marginal_var_pct,
        'component_var_pct': component_var_pct,
        'component_var_financeiro': component_var_pct * valor_carteira,
    })
    total = df['component_var_financeiro'].sum()
    df['contribuicao_pct'] = df['component_var_financeiro'] / total * 100 if total != 0 else 0
    return df.sort_values('component_var_financeiro', ascending=False).reset_index(drop=True)


def expected_shortfall_normal(pesos, cov_matrix, valor_carteira,
                              nivel_confianca=0.975, horizonte_dias=1):
    """ES sob normalidade — fórmula fechada."""
    pesos_alinhados = pesos.reindex(cov_matrix.index).fillna(0.0)
    w = pesos_alinhados.values
    var_p = float(w @ cov_matrix.values @ w)
    vol_p = np.sqrt(max(var_p, 0.0)) * np.sqrt(horizonte_dias)
    z_alpha = stats.norm.ppf(nivel_confianca)
    es_pct = vol_p * stats.norm.pdf(z_alpha) / (1 - nivel_confianca)
    return {
        'metodologia': 'ES Normal',
        'es_pct': es_pct,
        'es_financeiro': es_pct * valor_carteira,
    }


# ============================================================
# VaR MONTE CARLO
# ============================================================
def cholesky_correlated_shocks(cov_matrix, n_simulacoes, seed=None):
    """Choques normais correlacionados via decomposição de Cholesky."""
    if seed is not None:
        np.random.seed(seed)
    n_ativos = cov_matrix.shape[0]
    try:
        L = np.linalg.cholesky(cov_matrix.values)
    except np.linalg.LinAlgError:
        eps = 1e-8 * np.trace(cov_matrix.values) / n_ativos
        L = np.linalg.cholesky(cov_matrix.values + eps * np.eye(n_ativos))
    Z = np.random.standard_normal((n_simulacoes, n_ativos))
    return Z @ L.T


def var_monte_carlo_acoes(precos_atuais, quantidades, cov_matrix,
                          n_simulacoes=10000, nivel_confianca=0.95,
                          horizonte_dias=1, seed=42):
    """VaR Monte Carlo para carteira de ações via GBM correlacionado."""
    tickers = cov_matrix.index
    S0 = precos_atuais.reindex(tickers).values
    qtd = quantidades.reindex(tickers).fillna(0).values
    mu = np.zeros(len(tickers))
    sigma = np.sqrt(np.diag(cov_matrix.values))
    choques = cholesky_correlated_shocks(cov_matrix, n_simulacoes, seed)
    T = horizonte_dias
    drift = (mu - 0.5 * sigma ** 2) * T
    diffusion = np.sqrt(T) * choques
    log_retornos = drift + diffusion
    S_T = S0 * np.exp(log_retornos)
    valor_inicial = float((S0 * qtd).sum())
    valor_final = (S_T * qtd).sum(axis=1)
    pnl = valor_final - valor_inicial
    alpha = 1 - nivel_confianca
    var_financeiro = float(-np.percentile(pnl, alpha * 100))
    var_pct = var_financeiro / abs(valor_inicial) if valor_inicial != 0 else np.nan
    perdas_extremas = pnl[pnl <= -var_financeiro]
    es_financeiro = float(-perdas_extremas.mean()) if len(perdas_extremas) > 0 else np.nan
    return {
        'metodologia': 'Monte Carlo (GBM)',
        'var_pct': var_pct,
        'var_financeiro': var_financeiro,
        'es_financeiro': es_financeiro,
        'n_simulacoes': n_simulacoes,
        'pnl_simulado': pnl,
        'valor_carteira': valor_inicial,
    }


# ============================================================
# VaR DE OPÇÕES — QUATRO ABORDAGENS
# ============================================================
def var_opcoes_delta(df_opcoes, cov_matrix, nivel_confianca=0.95,
                     horizonte_dias=1, taxa_juros=0.115):
    """VaR via aproximação Delta — equivalente delta de ações."""
    exposicao_delta = {}
    for _, op in df_opcoes.iterrows():
        bs = BlackScholes(S=op['preco_subjacente'], K=op['strike'], T=op['T_anos'],
                          r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
        delta_equiv = bs.delta * op['quantidade'] * op['preco_subjacente']
        exposicao_delta[op['underlying']] = exposicao_delta.get(op['underlying'], 0) + delta_equiv

    expos = pd.Series(exposicao_delta)
    valor_bruto = expos.abs().sum()
    if valor_bruto < 1e-6:
        return {'metodologia': 'Delta (linear)', 'var_financeiro': 0.0, 'var_pct': 0.0}
    pesos = expos / valor_bruto
    pesos_alin = pesos.reindex(cov_matrix.index).fillna(0.0).values
    var_p = float(pesos_alin @ cov_matrix.values @ pesos_alin)
    vol_p = np.sqrt(max(var_p, 0)) * np.sqrt(horizonte_dias)
    z_alpha = stats.norm.ppf(nivel_confianca)
    var_pct = z_alpha * vol_p
    return {
        'metodologia': 'Delta (linear)',
        'var_financeiro': var_pct * valor_bruto,
        'var_pct': var_pct,
        'exposicao_delta': dict(expos),
    }


def var_opcoes_delta_gamma(df_opcoes, retornos_subjacentes,
                           nivel_confianca=0.95, horizonte_dias=1,
                           taxa_juros=0.115, n_simulacoes=10000, seed=42):
    """VaR via Delta-Gamma — simulação + expansão de Taylor de 2ª ordem."""
    rng = np.random.default_rng(seed)
    underlyings = df_opcoes['underlying'].unique().tolist()
    cov = retornos_subjacentes[underlyings].cov().values * horizonte_dias
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        L = np.linalg.cholesky(cov + 1e-8 * np.eye(len(underlyings)))
    Z = rng.standard_normal((n_simulacoes, len(underlyings)))
    choques_log = Z @ L.T

    pnl_simulado = np.zeros(n_simulacoes)
    for i, sub in enumerate(underlyings):
        S0_sub = df_opcoes[df_opcoes['underlying'] == sub]['preco_subjacente'].iloc[0]
        delta_S = S0_sub * (np.exp(choques_log[:, i]) - 1)
        for _, op in df_opcoes[df_opcoes['underlying'] == sub].iterrows():
            bs = BlackScholes(S=op['preco_subjacente'], K=op['strike'], T=op['T_anos'],
                              r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
            pnl_op = bs.delta*delta_S + 0.5*bs.gamma*delta_S**2
            pnl_simulado += op['quantidade'] * pnl_op

    var_fin = -np.percentile(pnl_simulado, (1-nivel_confianca)*100)
    return {
        'metodologia': 'Delta-Gamma',
        'var_financeiro': var_fin,
        'pnl_simulado': pnl_simulado,
    }


def var_opcoes_full_valuation_historico(df_opcoes, retornos_subjacentes,
                                        nivel_confianca=0.95, horizonte_dias=1,
                                        taxa_juros=0.115):
    """VaR Histórico com Full Valuation via Black-Scholes."""
    underlyings = df_opcoes['underlying'].unique().tolist()
    ret_subs = retornos_subjacentes[underlyings].dropna()
    n_obs = len(ret_subs)

    pnl_hist = np.zeros(n_obs)
    for _, op in df_opcoes.iterrows():
        S0 = op['preco_subjacente']
        bs0 = BlackScholes(S=S0, K=op['strike'], T=op['T_anos'],
                            r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
        choques = ret_subs[op['underlying']].values * np.sqrt(horizonte_dias)
        T_novo = max(op['T_anos'] - horizonte_dias/252, 1e-6)
        for i, ch in enumerate(choques):
            S_novo = S0 * np.exp(ch)
            bs_novo = BlackScholes(S=S_novo, K=op['strike'], T=T_novo,
                                    r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
            pnl_hist[i] += op['quantidade'] * (bs_novo.preco - bs0.preco)

    var_fin = -np.percentile(pnl_hist, (1-nivel_confianca)*100)
    return {
        'metodologia': 'Full Valuation Histórico',
        'var_financeiro': var_fin,
        'pnl_historico': pnl_hist,
        'n_observacoes': n_obs,
    }


def var_opcoes_montecarlo(df_opcoes, retornos_subjacentes,
                          nivel_confianca=0.95, horizonte_dias=1,
                          taxa_juros=0.115, n_simulacoes=10000,
                          chocar_vol=False, vol_choque_anual=0.10, seed=42):
    """VaR Monte Carlo com reprecificação completa (padrão-ouro)."""
    rng = np.random.default_rng(seed)
    underlyings = df_opcoes['underlying'].unique().tolist()
    cov = retornos_subjacentes[underlyings].cov().values * horizonte_dias
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        L = np.linalg.cholesky(cov + 1e-8 * np.eye(len(underlyings)))
    Z = rng.standard_normal((n_simulacoes, len(underlyings)))
    choques_log = Z @ L.T

    if chocar_vol:
        choques_vol = rng.normal(0, vol_choque_anual*np.sqrt(horizonte_dias/252),
                                  (n_simulacoes, len(df_opcoes)))
    else:
        choques_vol = np.zeros((n_simulacoes, len(df_opcoes)))

    pnl = np.zeros(n_simulacoes)
    u_idx = {u: i for i, u in enumerate(underlyings)}

    for op_idx, (_, op) in enumerate(df_opcoes.iterrows()):
        S0 = op['preco_subjacente']
        bs0 = BlackScholes(S=S0, K=op['strike'], T=op['T_anos'],
                            r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
        S_novos = S0 * np.exp(choques_log[:, u_idx[op['underlying']]])
        sigma_novos = np.clip(op['vol_implicita'] + choques_vol[:, op_idx], 0.01, 5.0)
        T_novo = max(op['T_anos'] - horizonte_dias/252, 1e-6)
        precos_novos = np.array([
            BlackScholes(S=s, K=op['strike'], T=T_novo, r=taxa_juros,
                          sigma=sg, tipo=op['tipo']).preco
            for s, sg in zip(S_novos, sigma_novos)
        ])
        pnl += op['quantidade'] * (precos_novos - bs0.preco)

    var_fin = -np.percentile(pnl, (1-nivel_confianca)*100)
    es_fin = -pnl[pnl <= -var_fin].mean() if len(pnl[pnl <= -var_fin]) > 0 else np.nan
    return {
        'metodologia': f'Monte Carlo ({"vega-aware" if chocar_vol else "vol constante"})',
        'var_financeiro': var_fin,
        'es_financeiro': es_fin,
        'pnl_simulado': pnl,
    }


# ============================================================
# CLASSIFICAÇÃO DE LIMITES
# ============================================================
def classificar_utilizacao(var_calculado: float, limite: float) -> dict:
    """Tabela verde/amarelo/vermelho do enunciado."""
    if limite <= 0:
        return {'status': 'Inválido', 'cor': '⚫', 'utilizacao_pct': 0,
                'breach': False, 'limite_disponivel': 0}
    utilizacao = var_calculado / limite
    if utilizacao <= 0.70:
        status, cor = 'Verde', '🟢'
    elif utilizacao <= 1.00:
        status, cor = 'Amarelo', '🟡'
    else:
        status, cor = 'Vermelho', '🔴'
    return {
        'utilizacao': utilizacao,
        'utilizacao_pct': utilizacao * 100,
        'status': status,
        'cor': cor,
        'breach': utilizacao > 1.00,
        'limite_disponivel': max(limite - var_calculado, 0.0),
    }


# ============================================================
# STRESS TESTING
# ============================================================
CENARIOS_STRESS = {
    'Joesley Day (17/05/2017)': {
        'PETR4.SA': -0.15, 'VALE3.SA': -0.09, 'ITUB4.SA': -0.14,
        'BBDC4.SA': -0.14, 'ABEV3.SA': -0.08, 'B3SA3.SA': -0.10,
        'MGLU3.SA': -0.18, 'WEGE3.SA': -0.08,
    },
    'COVID Crash (16/03/2020)': {
        'PETR4.SA': -0.20, 'VALE3.SA': -0.13, 'ITUB4.SA': -0.15,
        'BBDC4.SA': -0.15, 'ABEV3.SA': -0.12, 'B3SA3.SA': -0.18,
        'MGLU3.SA': -0.25, 'WEGE3.SA': -0.14,
    },
    'Eleições 1º Turno (08/10/2018)': {
        'PETR4.SA': 0.13, 'VALE3.SA': 0.05, 'ITUB4.SA': 0.06,
        'BBDC4.SA': 0.06, 'ABEV3.SA': 0.04, 'B3SA3.SA': 0.08,
        'MGLU3.SA': 0.10, 'WEGE3.SA': 0.05,
    },
    'Choque hipotético -10% Ibovespa': {
        ticker: -0.10 for ticker in
        ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'ABEV3.SA',
         'B3SA3.SA', 'MGLU3.SA', 'WEGE3.SA']
    },
    'Choque hipotético +10% Ibovespa': {
        ticker: 0.10 for ticker in
        ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'ABEV3.SA',
         'B3SA3.SA', 'MGLU3.SA', 'WEGE3.SA']
    },
}


def stress_test_acoes(df_posicoes, cenario_choques):
    """Stress test determinístico para carteira de ações."""
    pnl_total = 0.0
    detalhes = []
    for _, pos in df_posicoes.iterrows():
        if pos['tipo'] == 'acao':
            choque = cenario_choques.get(pos['ativo'], 0.0)
            S0 = pos['preco']
            qtd = pos['quantidade']
            pnl = (S0 * choque) * qtd
            pnl_total += pnl
            detalhes.append({
                'ativo': pos['ativo'],
                'choque_pct': choque * 100,
                'pnl': pnl,
            })
    return pnl_total, pd.DataFrame(detalhes)


def stress_test_opcoes(df_opcoes, cenario_choques, choque_vol_pp=0,
                        taxa_juros=0.115):
    """Stress test para opções via reprecificação Black-Scholes."""
    pnl_total = 0.0
    detalhes = []
    for _, op in df_opcoes.iterrows():
        ch_sub = cenario_choques.get(op['underlying'], 0.0)
        S_stress = op['preco_subjacente'] * (1 + ch_sub)
        sigma_stress = max(op['vol_implicita'] + choque_vol_pp, 0.01)
        bs_atual = BlackScholes(S=op['preco_subjacente'], K=op['strike'], T=op['T_anos'],
                                 r=taxa_juros, sigma=op['vol_implicita'], tipo=op['tipo'])
        bs_stress = BlackScholes(S=S_stress, K=op['strike'], T=op['T_anos'],
                                  r=taxa_juros, sigma=sigma_stress, tipo=op['tipo'])
        pnl_op = op['quantidade'] * (bs_stress.preco - bs_atual.preco)
        pnl_total += pnl_op
        detalhes.append({
            'ativo': op['ativo'],
            'choque_subjacente_pct': ch_sub * 100,
            'choque_vol_pp': choque_vol_pp * 100,
            'preco_pre': bs_atual.preco,
            'preco_pos': bs_stress.preco,
            'pnl': pnl_op,
        })
    return pnl_total, pd.DataFrame(detalhes)
