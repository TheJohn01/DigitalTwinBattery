import streamlit as st
try:
    import pybamm
except Exception:
    # A aplicação continua a abrir mesmo sem PyBaMM; a simulação física
    # será tentada quando a biblioteca estiver disponível e, se necessário,
    # usa a contingência numérica explicitamente sinalizada.
    pybamm = None
import json
import pandas as pd
import numpy as np

try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:
    px = None
    go = None

# Importação dos módulos externos de análise
TEA_IMPORT_ERROR = None
LCA_IMPORT_ERROR = None
try:
    from analise_economica import calcular_tea
except Exception as exc:
    calcular_tea = None
    TEA_IMPORT_ERROR = exc

try:
    from analise_ambiental import calcular_lca_bateria
except Exception as exc:
    calcular_lca_bateria = None
    LCA_IMPORT_ERROR = exc

# Importação da única fonte de verdade para a física eletroquímica.
# Tolerante: se o módulo ou o PyBaMM faltarem, a app continua a abrir e
# usa a contingência numérica interna (definida mais abaixo).
FQ_IMPORT_ERROR = None
try:
    from fase1_1_quimica import (
        CAPEX_BASE_EUR_KWH,
        CARBONO_FABRICO_KG_CO2_KWH,
        DEGRADACAO_QUIMICA,
        TENSOES_NOMINAIS,
        _quimica_curta,
        _capex_quimica,
        _safe_float,
        _carbono_nivelado,
        _normalizar_taxas,
        _parametros_quimica,
        _parametros_termicos,
        _parametros_sei,
        _construir_experiencia,
        _solver_robusto,
        _criar_modelo_e_parametros,
        _texto_erro,
        _executar_pybamm,
        comparar_quimicas as comparar_multiquimica,
    )
except Exception as exc:
    # Fallbacks mínimos para que a app não quebre no arranque; a simulação
    # física recairá na contingência numérica.
    FQ_IMPORT_ERROR = exc
    CAPEX_BASE_EUR_KWH = {"NMC": 125.0, "LFP": 95.0, "NCA": 130.0, "Chumbo-Ácido": 75.0}
    CARBONO_FABRICO_KG_CO2_KWH = {"NMC": 85.0, "LFP": 55.0, "NCA": 90.0, "Chumbo-Ácido": 45.0}
    DEGRADACAO_QUIMICA = {
        "NMC": (0.000045, 0.000010, 0.000003),
        "LFP": (0.000025, 0.000006, 0.000002),
        "NCA": (0.000050, 0.000012, 0.000003),
        "Chumbo-Ácido": (0.000120, 0.000030, 0.000008),
    }
    TENSOES_NOMINAIS = {
        "NMC/Grafite (Chen 2020)": 3.7,
        "LFP/Grafite (Prada 2013)": 3.2,
        "NCA/Grafite (Ai 2020)": 3.6,
        "Chumbo-Ácido (Sulzer 2019)": 2.0,
    }
    _quimica_curta = lambda tag: str(tag)
    _capex_quimica = lambda tag: 130.0
    _safe_float = lambda x, default=0.0: 0.0
    _carbono_nivelado = lambda *a, **k: 0.0
    _normalizar_taxas = lambda a, b: (float(a), float(b))
    _parametros_quimica = None
    _parametros_termicos = None
    _parametros_sei = None
    _construir_experiencia = None
    _solver_robusto = None
    _criar_modelo_e_parametros = None
    _texto_erro = lambda e: str(e)
    _executar_pybamm = None
    comparar_multiquimica = None

def _plotly_disponivel():
    """Indica se Plotly foi importado corretamente."""
    return px is not None and go is not None


def _mostrar_plotly(fig):
    """Mostra um gráfico Plotly sem deixar uma incompatibilidade de Streamlit
    derrubar o dashboard."""
    try:
        st.plotly_chart(fig, use_container_width=True)
        return True
    except TypeError:
        # Compatibilidade com versões em que a assinatura mudou.
        try:
            st.plotly_chart(fig, width="stretch")
            return True
        except Exception:
            return False
    except Exception:
        return False


st.set_page_config(page_title="Digital Twin Industrial - Bateria", layout="wide")

st.title("🔋 Digital Twin: Simulador Eletroquímico de Escala Industrial")
st.write("Simulação física multiquímica com submodelos otimizados por tecnologia e exportação sanitizada.")

def _finite_nonnegative(v, default=0.0):
    try:
        x=float(v)
        return x if np.isfinite(x) and x>=0 else float(default)
    except Exception:
        return float(default)

# =====================================================================
# 1. Funções de Extração Robusta
# =====================================================================
def extrair_capacidade(cycle):
    """Extrai a capacidade de descarga [Ah] de UM ciclo, com fallback multinível."""
    try:
        if len(cycle.steps) > 0:
            entries = cycle.steps[0]["Discharge capacity [A.h]"].entries
            if len(entries) > 0:
                return abs(float(entries[-1]))
    except Exception:
        pass
    try:
        tempo_s = cycle["Time [s]"].entries
        corrente_a = cycle["Current [A]"].entries
        if len(tempo_s) > 1:
            dt = np.diff(tempo_s, prepend=tempo_s[0])
            corrente_descarga = np.where(corrente_a > 0, corrente_a, 0)
            return abs(float(np.sum(corrente_descarga * dt) / 3600.0))
    except Exception:
        pass
    return 0.0


def extrair_capacidades_todos_ciclos(solution):
    """Devolve um array com a capacidade de descarga [Ah] por ciclo."""
    try:
        caps = np.array(solution.summary_variables["Capacity [A.h]"], dtype=float)
        if len(caps) == len(solution.cycles):
            return caps
    except Exception:
        pass
    return np.array([extrair_capacidade(c) for c in solution.cycles], dtype=float)


def extrair_temperatura_ciclo(cycle, temp_amb_fallback):
    """Extrai a série temporal de temperatura (°C) do ciclo sem aceder diretamente a .variables instáveis."""
    chaves_c = [
        "X-averaged cell temperature [C]",
        "Cell temperature [C]",
        "Volume-averaged cell temperature [C]",
        "X-averaged battery temperature [C]"
    ]
    chaves_k = [
        "X-averaged cell temperature [K]",
        "Cell temperature [K]",
        "Volume-averaged cell temperature [K]",
        "X-averaged battery temperature [K]"
    ]

    for key in chaves_c:
        try:
            return cycle[key].entries
        except Exception:
            pass

    for key in chaves_k:
        try:
            return cycle[key].entries - 273.15
        except Exception:
            pass

    try:
        n_pontos = len(cycle["Time [s]"].entries)
    except Exception:
        n_pontos = 1

    return np.full(n_pontos, float(temp_amb_fallback))



# =====================================================================
# 1B. Métricas de eficiência, TEA/LCA avançados e comparação
# =====================================================================
def calcular_eficiencia_ciclo_a_ciclo(df_series):
    """Calcula eficiência coulômbica e energética por ciclo.
    Convenção PyBaMM: corrente positiva = descarga; negativa = carga.
    Usa integração trapezoidal e protege divisões por zero/NaN.
    """
    if df_series is None or df_series.empty:
        return pd.DataFrame(columns=[
            "Ciclo", "Carga [Ah]", "Descarga [Ah]", "Eficiência Coulômbica [%]",
            "Energia Carga [Wh]", "Energia Descarga [Wh]", "Eficiência Energética [%]"
        ])
    rows=[]
    for ciclo, g in df_series.groupby("Ciclo", sort=True):
        g=g.sort_values("Tempo [s]")
        t=g["Tempo [s]"].to_numpy(dtype=float)
        i=g["Corrente [A]"].to_numpy(dtype=float)
        v=g["Tensão [V]"].to_numpy(dtype=float)
        mask=np.isfinite(t)&np.isfinite(i)&np.isfinite(v)
        t,i,v=t[mask],i[mask],v[mask]
        if len(t)<2:
            rows.append({"Ciclo":int(ciclo),"Carga [Ah]":0.0,"Descarga [Ah]":0.0,
                         "Eficiência Coulômbica [%]":0.0,"Energia Carga [Wh]":0.0,
                         "Energia Descarga [Wh]":0.0,"Eficiência Energética [%]":0.0})
            continue
        # Integração de carga e descarga separadamente evita cancelamento.
        qd=(np.trapezoid if hasattr(np, "trapezoid") else np.trapz)(np.clip(i,0,None),t)/3600.0
        qc=(np.trapezoid if hasattr(np, "trapezoid") else np.trapz)(np.clip(-i,0,None),t)/3600.0
        # IMPORTANTE: não usar o nome `pd` aqui, porque `pd` é o módulo pandas.
        # Um escalar numpy.float64 nesse nome faria `pd.DataFrame(...)` falhar.
        energia_descarga_wh=(np.trapezoid if hasattr(np, "trapezoid") else np.trapz)(np.clip(v*i,0,None),t)/3600.0
        energia_carga_wh=(np.trapezoid if hasattr(np, "trapezoid") else np.trapz)(np.clip(-v*i,0,None),t)/3600.0
        ce=100.0*qd/qc if qc>1e-12 else 0.0
        ee=100.0*energia_descarga_wh/energia_carga_wh if energia_carga_wh>1e-12 else 0.0
        vals=[qd,qc,energia_descarga_wh,energia_carga_wh,ce,ee]
        vals=[float(x) if np.isfinite(x) else 0.0 for x in vals]
        rows.append({"Ciclo":int(ciclo),"Carga [Ah]":round(vals[1],6),
                     "Descarga [Ah]":round(vals[0],6),
                     "Eficiência Coulômbica [%]":round(min(max(vals[4],0),200),4),
                     "Energia Carga [Wh]":round(vals[3],6),
                     "Energia Descarga [Wh]":round(vals[2],6),
                     "Eficiência Energética [%]":round(min(max(vals[5],0),200),4)})
    return pd.DataFrame(rows)

def _safe_array(values, default=0.0):
    """Converte sequências numéricas em arrays finitos, sem propagar NaN/inf."""
    try:
        arr = np.asarray(values, dtype=float)
        return np.nan_to_num(arr, nan=float(default), posinf=float(default), neginf=float(default))
    except Exception:
        return np.asarray([], dtype=float)

def calcular_sensibilidade_tea(capex, eletricidade, capacidade_kwh, degradacao_anual,
                               ciclos_dia, spread_arbitragem=0.10):
    """Sensibilidade de primeira ordem, independente do módulo TEA externo.
    Varia cada entrada ±20% e calcula um proxy de LCOS anualizado.
    """
    capex=max(_safe_float(capex,130),0.0)
    elec=max(_safe_float(eletricidade,.2),0.0)
    cap=max(_safe_float(capacidade_kwh,.1),.1)
    deg=max(_safe_float(degradacao_anual,0),0.0)
    cpd=max(_safe_float(ciclos_dia,1),0.01)
    spread=max(_safe_float(spread_arbitragem,.10),0.0)
    vida_anos=max(1.0/(deg/100.0) if deg>0 else 15.0,0.25)
    throughput=max(cap*cpd*365*vida_anos,cap)
    base=(capex*cap + elec*throughput*0.08 - spread*throughput*0.5)/throughput
    base=max(base,0.0)
    defs=[
        ("CAPEX",capex,lambda x: (x*cap + elec*throughput*0.08-spread*throughput*.5)/throughput),
        ("Preço eletricidade",elec,lambda x: (capex*cap + x*throughput*.08-spread*throughput*.5)/throughput),
        ("Spread arbitragem",spread,lambda x: (capex*cap + elec*throughput*.08-x*throughput*.5)/throughput),
    ]
    rows=[]
    for nome,val,fn in defs:
        low=max(val*.8,0.0); high=val*1.2
        vl=max(_safe_float(fn(low),base),0.0); vh=max(_safe_float(fn(high),base),0.0)
        rows.append({"Parâmetro":nome,"Variação baixa (-20%)":vl-base,
                     "Variação alta (+20%)":vh-base,"Base":base,
                     "Baixo":vl,"Alto":vh})
    return pd.DataFrame(rows)

def calcular_valor_segunda_vida(capacidade_kwh, soh_final, capex_kwh,
                                custo_eletricidade, spread=0.10, anos=8):
    """Modelo económico transparente para EV -> armazenamento estacionário.
    O valor é um proxy; não substitui uma avaliação financeira completa.
    """
    cap=max(_safe_float(capacidade_kwh,.1),.1)
    soh=max(min(_safe_float(soh_final,80),100),0)/100.0
    capex=max(_safe_float(capex_kwh,130),0)
    elec=max(_safe_float(custo_eletricidade,.2),0)
    spread=max(_safe_float(spread,.1),0)
    usable=cap*soh*.80
    ciclos_ano=250
    throughput=usable*ciclos_ano*max(int(anos),1)
    receita=throughput*spread
    opex=throughput*elec*.05
    valor_bruto=max(receita-opex,0)
    valor_atual=max(valor_bruto-0.15*capex*cap,0)
    return pd.DataFrame([{
        "Capacidade reutilizável [kWh]":round(usable,3),
        "Vida 2ª vida [anos]":int(max(anos,1)),
        "Throughput [kWh]":round(throughput,1),
        "Receita arbitragem [€]":round(receita,2),
        "OPEX estimado [€]":round(opex,2),
        "Valor líquido indicativo 2ª vida [€]":round(valor_atual,2),
    }])

def indicadores_lca_avancados(capacidade_kwh, massa_kg, quimica):
    """Indicadores de screening quando o módulo LCA não fornece inventário
    de água/ecotoxicidade. São fatores comparativos, não uma declaração ISO.
    """
    fatores={
        "NMC":(55.0,1.00),"LFP":(38.0,.65),"NCA":(58.0,1.05),"Chumbo-Ácido":(25.0,.80)
    }
    agua,eco=fatores.get(quimica,(45.0,.9))
    return pd.DataFrame([
        {"Indicador":"Pegada hídrica — screening","Valor":round(max(capacidade_kwh,0)*agua,2),
         "Unidade":"L/kWh de capacidade","Nota":"Estimativa comparativa; requer inventário LCA para ISO 14040."},
        {"Indicador":"Ecotoxicidade — screening","Valor":round(max(massa_kg,0)*eco,2),
         "Unidade":"unidades relativas","Nota":"Indicador proxy; não é LCIA certificado."},
    ])

# =====================================================================
# 2. Barra Lateral - Configuração
# =====================================================================
st.sidebar.header("⚙️ Modelo & Operação")

modo_simulacao = st.sidebar.radio(
    "Resolução do Modelo",
    options=["SPMe (Industrial - Alta Velocidade)", "DFN (Físico Detalhado - Alta Precisão)"],
    help="SPMe permite simular até 1000 ciclos em segundos."
)

tecnologia = st.sidebar.selectbox(
    "Química / Tecnologia",
    options=["NMC/Grafite (Chen 2020)", "LFP/Grafite (Prada 2013)", "NCA/Grafite (Ai 2020)", "Chumbo-Ácido (Sulzer 2019)"]
)

taxa_carga = st.sidebar.slider("Taxa de Carga (C-rate)", 0.5, 4.0, 1.5, 0.5)
taxa_descarga = st.sidebar.slider("Taxa de Descarga (C-rate)", 0.5, 3.0, 1.5, 0.5)

max_ciclos = 1000 if "SPMe" in modo_simulacao else 50
num_ciclos = st.sidebar.slider("Número de Ciclos", 1, max_ciclos, 100 if max_ciclos >= 100 else 10, 5 if max_ciclos >= 100 else 1)

st.sidebar.header("🌡️ Condições Térmicas")
temp_amb_c = st.sidebar.slider("Temperatura Ambiente (°C)", 5, 45, 25, 5)
h_cooling = st.sidebar.slider("Coef. Arrefecimento h (W/m²K)", 5, 100, 10, 5)

st.sidebar.header("🔋 Configuração do Pack")
num_celulas_pack = st.sidebar.number_input(
    "Nº de Células no Pack (associação equivalente)",
    min_value=1, value=100, step=10,
    help="Escala a capacidade da célula simulada até à escala do pack, antes de alimentar a TEA/LCA."
)
massa_por_celula_kg = st.sidebar.number_input(
    "Massa Estimada por Célula (kg)", min_value=0.01, value=0.5, step=0.05,
    help="Usada para estimar a massa total do pack (kg) na análise ambiental (LCA)."
)

st.sidebar.header("💰 Parâmetros TEA")
capex_kwh = st.sidebar.number_input(
    "CAPEX (€/kWh) — química selecionada",
    min_value=0.0, value=_capex_quimica(tecnologia), step=5.0
)
custo_eletr = st.sidebar.number_input("Custo Eletricidade (€/kWh)", value=0.20, step=0.01)
spread_arbitragem = st.sidebar.number_input("Spread de Arbitragem (€/kWh)", min_value=0.0, value=0.10, step=0.01)
anos_segunda_vida = st.sidebar.number_input("Vida da 2ª vida (anos)", min_value=1, max_value=20, value=8, step=1)
ciclos_por_ano = st.sidebar.number_input(
    "Ciclos Equivalentes / Ano", min_value=1, value=365, step=1,
    help="Usado para converter a degradação simulada numa taxa anual e na projeção da TEA."
)

st.sidebar.header("🌱 Parâmetros LCA")
aplicacao = st.sidebar.radio("Perfil de Aplicação", ["Veicular (EV)", "Estacionário"])
aplicacao_veicular = aplicacao == "Veicular (EV)"
if aplicacao_veicular:
    distancia_km = st.sidebar.number_input("Vida Útil Estimada (km)", value=200000, step=10000)
    consumo_kwh_km = st.sidebar.number_input("Consumo Energético (kWh/km)", value=0.16, step=0.01)
else:
    distancia_km = 200000.0
    consumo_kwh_km = 0.16


# =====================================================================
# 3. Construção + Resolução da Simulação
# =====================================================================

class _SyntheticVariable:
    """Pequeno adaptador para manter a mesma API de acesso usada pela UI."""
    def __init__(self, entries):
        self.entries = np.asarray(entries, dtype=float)


class _SyntheticCycle:
    """Ciclo de contingência usado apenas se o solver PyBaMM não conseguir convergir."""
    def __init__(self, data):
        self._data = {k: _SyntheticVariable(v) for k, v in data.items()}
        self.steps = []

    def __getitem__(self, key):
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]


class _SyntheticSolution:
    def __init__(self, cycles, capacities):
        self.cycles = cycles
        self.summary_variables = {"Capacity [A.h]": np.asarray(capacities, dtype=float)}




def _criar_fallback_numerico(modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                             num_ciclos, temp_amb_c, h_cooling, motivo):
    """Fallback determinístico para garantir que a aplicação continua utilizável.

    Não inventa um 'resultado PyBaMM': gera uma curva operacional simplificada,
    explicitamente marcada como contingência. Serve para que uma falha de
    convergência nunca transforme a aplicação num erro de execução e para que
    TEA/LCA/exportação continuem disponíveis.
    """
    p = _parametros_quimica(tecnologia)
    carga, descarga = _normalizar_taxas(taxa_carga, taxa_descarga)

    # Número de pontos limitado para não explodir memória em 1000 ciclos.
    npts = 36 if num_ciclos > 100 else 60
    dt = 60.0
    ciclos = []
    capacidades = [p["capacidade_base_ah"]]

    for ciclo in range(int(num_ciclos) + 1):
        fade = min(0.35, 0.00008 * ciclo * (1.0 + 0.15 * max(carga, descarga)))
        cap = p["capacidade_base_ah"] * (1.0 - fade)
        capacidades.append(cap) if ciclo > 0 else None

        t = np.arange(npts, dtype=float) * dt
        fase = np.linspace(0.0, 1.0, npts)
        # Perfil carga/descarga/rest simples, mas contínuo e finito.
        corrente = np.where(fase < 0.45, descarga * cap,
                    np.where(fase < 0.90, -carga * cap, 0.0))
        tensao = p["v_nom"] + 0.22 * np.cos(2 * np.pi * fase)
        tensao -= 0.025 * np.abs(corrente) / max(max(carga, descarga), 0.1)
        tensao = np.clip(tensao, p["v_min"], p["v_max"])
        temp = float(temp_amb_c) + (
            1.5 + 1.5 * abs(corrente) / max(max(carga, descarga) * cap, 1e-9)
        ) * (float(h_cooling) / max(float(h_cooling), 5.0))
        temp = np.full(npts, temp, dtype=float)

        data = {
            "Time [s]": t,
            "Terminal voltage [V]": tensao,
            "Current [A]": corrente,
            "X-averaged cell temperature [C]": temp,
        }
        if p["sei"]:
            sei = 5e-9 * (1.0 + 0.012 * ciclo)
            data["X-averaged negative SEI thickness [m]"] = np.full(npts, sei)
        ciclos.append(_SyntheticCycle(data))

    # A UI descarta o primeiro ciclo como inicialização.
    if len(capacidades) < len(ciclos):
        capacidades.extend([capacidades[-1]] * (len(ciclos) - len(capacidades)))
    capacidades = np.asarray(capacidades[:len(ciclos)], dtype=float)

    meta = {
        "tem_sei": p["sei"],
        "quimica_tag": p["tag"],
        "modo_efetivo": "Contingência numérica",
        "fallback": True,
        "taxa_carga_efetiva": carga,
        "taxa_descarga_efetiva": descarga,
        "mensagem_fallback": motivo,
        "synthetic": True,
    }
    return _SyntheticSolution(ciclos, capacidades), meta


@st.cache_data(show_spinner=False)
def executar_simulacao(modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                       num_ciclos, temp_amb_c, h_cooling):
    """Executa a simulação com recuperação multinível.

    Garantia operacional: uma combinação de parâmetros nunca propaga uma
    exceção para a interface. Primeiro é tentada a simulação física pedida;
    depois são ativados fallbacks de compatibilidade/convergência; por fim,
    existe uma contingência numérica explícita para manter TEA/LCA/exportação.
    """
    try:
        sol, meta, err = _executar_pybamm(
            modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
            num_ciclos, temp_amb_c, h_cooling
        )
        if sol is not None:
            return sol, meta, None
        return (
            *_criar_fallback_numerico(
                modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                num_ciclos, temp_amb_c, h_cooling, err or "Falha de convergência."
            ),
            None,
        )
    except Exception as err:
        try:
            sol, meta = _criar_fallback_numerico(
                modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                num_ciclos, temp_amb_c, h_cooling, _texto_erro(err)
            )
            return sol, meta, None
        except Exception as fallback_err:
            # Último nível: nunca deixa a função levantar a exceção.
            return None, None, f"Falha irrecuperável: {_texto_erro(fallback_err)}"


# =====================================================================
# 4. Gestão de Estado e Apresentação de Resultados
# =====================================================================
if st.sidebar.button("🚀 Executar Simulação", use_container_width=True):
    with st.spinner(f"A simular {num_ciclos} ciclos de operação..."):
        sol, meta, err = executar_simulacao(
            modo_simulacao, tecnologia, taxa_carga, taxa_descarga, num_ciclos, temp_amb_c, h_cooling
        )
        if err or sol is None or meta is None:
            # Último guardião da interface: nunca interromper a aplicação com
            # st.stop() por uma falha numérica.
            try:
                sol, meta = _criar_fallback_numerico(
                    modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                    num_ciclos, temp_amb_c, h_cooling,
                    err or "Resultado inválido devolvido pelo solver."
                )
                st.session_state["sim_result"] = (sol, meta)
            except Exception as final_err:
                st.error(f"Não foi possível gerar sequer a contingência numérica: {_texto_erro(final_err)}")
        else:
            st.session_state["sim_result"] = (sol, meta)

# Renderização persistente após interações na UI
if "sim_result" in st.session_state:
    solution, metadata = st.session_state["sim_result"]
    tem_sei = bool(metadata.get("tem_sei", False))
    quimica_tag = metadata.get("quimica_tag", "Desconhecida")

    if metadata.get("fallback"):
        st.warning(
            "⚠️ A configuração pedida não convergiu com a física original. "
            f"Foi ativado automaticamente: **{metadata.get('modo_efetivo', 'fallback')}**. "
            "As condições escolhidas continuam a ser mostradas na interface; "
            "o detalhe da recuperação está disponível abaixo."
        )
        if metadata.get("mensagem_fallback"):
            with st.expander("Detalhe técnico da recuperação"):
                st.code(metadata["mensagem_fallback"])

    try:
        ciclos_obtidos = max(len(solution.cycles) - 1, 1)
    except Exception:
        ciclos_obtidos = 1

    if ciclos_obtidos < num_ciclos:
        st.warning(
            f"⚠️ A experiência terminou ao fim de {ciclos_obtidos} ciclos válidos "
            f"(de {num_ciclos} pedidos). Os resultados refletem os ciclos simulados."
        )

    # --- CAPACIDADE POR CICLO E SOH FÍSICO REAL ---
    capacidades_todos_ciclos = extrair_capacidades_todos_ciclos(solution)
    caps_ciclos = capacidades_todos_ciclos[1:] if len(capacidades_todos_ciclos) > 1 else capacidades_todos_ciclos
    caps_ciclos = np.asarray(caps_ciclos, dtype=float)
    caps_ciclos = caps_ciclos[np.isfinite(caps_ciclos)]
    cap_ref = float(np.max(caps_ciclos)) if caps_ciclos.size and np.max(caps_ciclos) > 0 else 1.0

    dados_resumo = []
    for idx, cycle in enumerate(solution.cycles[1:], start=1):
        cap_act = float(capacidades_todos_ciclos[idx]) if idx < len(capacidades_todos_ciclos) else 0.0
        if not np.isfinite(cap_act):
            cap_act = 0.0
        soh_real = max(0.0, min(100.0, (cap_act / cap_ref) * 100.0))

        temp_vals = np.asarray(extrair_temperatura_ciclo(cycle, temp_amb_c), dtype=float)
        temp_vals = temp_vals[np.isfinite(temp_vals)]
        temp_max = float(np.max(temp_vals)) if temp_vals.size else float(temp_amb_c)

        sei_nm = 0.0
        if tem_sei:
            try:
                sei_nm = float(cycle["X-averaged negative SEI thickness [m]"].entries[-1]) * 1e9
            except Exception:
                try:
                    sei_nm = float(cycle["X-averaged SEI thickness [m]"].entries[-1]) * 1e9
                except Exception:
                    sei_nm = 0.0

        dados_resumo.append({
            "Ciclo": idx,
            "Capacidade [Ah]": round(cap_act, 4),
            "SOH [%]": round(soh_real, 2),
            "Temp Máx [°C]": round(temp_max, 1),
            "SEI [nm]": round(sei_nm, 2)
        })

    df_resumo = pd.DataFrame(dados_resumo)

    # --- Conversão Ah -> kWh e massa do PACK ---
    v_nom = TENSOES_NOMINAIS.get(tecnologia, 3.7)
    capacidade_pack_kwh = (cap_ref * v_nom * num_celulas_pack) / 1000.0
    massa_pack_kg = num_celulas_pack * massa_por_celula_kg

    # --- Série Temporal ---
    v_nom = TENSOES_NOMINAIS.get(tecnologia, 3.7)
    series_dados = []
    try:
        ciclos_series = solution.cycles[1:] if len(solution.cycles) > 1 else solution.cycles
        t_zero_ref = float(ciclos_series[0]["Time [s]"].entries[0])
    except Exception:
        ciclos_series = []
        t_zero_ref = 0.0

    for idx, cycle in enumerate(ciclos_series, start=1):
        try:
            t_array = np.asarray(cycle["Time [s]"].entries, dtype=float) - t_zero_ref
            v_array = np.asarray(cycle["Terminal voltage [V]"].entries, dtype=float)
            i_array = np.asarray(cycle["Current [A]"].entries, dtype=float)
            temp_array = np.asarray(extrair_temperatura_ciclo(cycle, temp_amb_c), dtype=float)
            n = min(len(t_array), len(v_array), len(i_array), len(temp_array))
            if n == 0:
                continue
            t_array, v_array, i_array, temp_array = (
                t_array[:n], v_array[:n], i_array[:n], temp_array[:n]
            )
            p_array = v_array * i_array
        except Exception:
            continue

        for t, v, i, p, temp in zip(t_array, v_array, i_array, p_array, temp_array):
            series_dados.append({
                "Ciclo": idx,
                "Tempo [s]": round(float(t), 2),
                "Tempo [min]": round(float(t / 60.0), 2),
                "Tensão [V]": round(float(v), 4),
                "Corrente [A]": round(float(i), 3),
                "Potência [W]": round(float(p), 3),
                "Temperatura [°C]": round(float(temp), 2)
            })

    df_series = pd.DataFrame(series_dados)
    if df_series.empty:
        df_series = pd.DataFrame({
            "Ciclo": [1], "Tempo [s]": [0.0], "Tempo [min]": [0.0],
            "Tensão [V]": [float(v_nom if 'v_nom' in locals() else TENSOES_NOMINAIS.get(tecnologia, 3.7))],
            "Corrente [A]": [0.0], "Potência [W]": [0.0],
            "Temperatura [°C]": [float(temp_amb_c)]
        })
    else:
        df_series = df_series.drop_duplicates(subset=["Ciclo", "Tempo [s]"])

    # --- KPIs ---
    st.markdown("### Indicadores Globais do Sistema")
    col1, col2, col3, col4, col5 = st.columns(5)
    soh_final = df_resumo["SOH [%]"].iloc[-1]
    col1.metric("SOH Final", f"{soh_final:.2f} %", delta=f"{soh_final - 100:.2f} %")
    col2.metric("Capacidade Restante", f"{df_resumo['Capacidade [Ah]'].iloc[-1]:.2f} Ah")
    col3.metric("Capacidade do Pack", f"{capacidade_pack_kwh:.2f} kWh")
    col4.metric("Temperatura Máxima", f"{df_resumo['Temp Máx [°C]'].max():.1f} °C")
    col5.metric("Espessura SEI Ânodo", f"{df_resumo['SEI [nm]'].iloc[-1]:.1f} nm" if tem_sei else "N/A")
    st.caption(
        f"Pack: {num_celulas_pack} células ({v_nom} V nominal, {quimica_tag}) × "
        f"{cap_ref:.2f} Ah de referência → ≈ {capacidade_pack_kwh:.2f} kWh úteis, ≈ {massa_pack_kg:.1f} kg."
    )

    tab_fisica, tab_tea, tab_lca, tab_dados = st.tabs([
        "⚡ Eletroquímica & Térmica",
        "💰 Análise Económica (TEA)",
        "🌱 Análise Ambiental (LCA)",
        "📄 Exportação de Dados"
    ])

    with tab_fisica:
        df_eficiencia = calcular_eficiencia_ciclo_a_ciclo(df_series)
        st.markdown("#### Eficiência ciclo a ciclo")
        st.dataframe(df_eficiencia, use_container_width=True)
        if not df_eficiencia.empty:
            if _plotly_disponivel():
                fig_eff = go.Figure()
                fig_eff.add_trace(go.Scatter(x=df_eficiencia["Ciclo"], y=df_eficiencia["Eficiência Coulômbica [%]"], mode="lines+markers", name="Coulômbica"))
                fig_eff.add_trace(go.Scatter(x=df_eficiencia["Ciclo"], y=df_eficiencia["Eficiência Energética [%]"], mode="lines+markers", name="Energética"))
                fig_eff.update_layout(title="Eficiência por ciclo", xaxis_title="Ciclo", yaxis_title="Eficiência [%]", hovermode="x unified")
                _mostrar_plotly(fig_eff)

        if _plotly_disponivel():
            fig1=px.line(df_resumo,x="Ciclo",y="SOH [%]",markers=True,title="Retenção de Capacidade (SOH)")
            fig2=px.line(df_series,x="Tempo [min]",y="Tensão [V]",color="Ciclo",title="Perfil Contínuo de Tensão")
            fig3=px.line(df_series,x="Tempo [min]",y="Temperatura [°C]",color="Ciclo",title="Evolução Térmica Dinâmica")
            _mostrar_plotly(fig1)
            _mostrar_plotly(fig2)
            _mostrar_plotly(fig3)
        else:
            st.info("Plotly não está instalado; os dados permanecem disponíveis nas tabelas.")
        if soh_final >= 99.99:
            st.info("ℹ️ Não foi observada perda de capacidade mensurável no número de ciclos simulado.")

    with tab_tea:
        st.markdown("#### Indicadores Financeiros (Módulo `analise_economica.py`)")
        if calcular_tea is not None:
            perda_pct_periodo = max(100.0 - float(soh_final), 0.0)
            anos_decorridos = max(float(num_ciclos) / max(float(ciclos_por_ano), 1.0), 1.0 / 365.0)
            degradacao_anual_pct = perda_pct_periodo / anos_decorridos
            ciclos_por_dia = ciclos_por_ano / 365.0

            try:
                df_tea = calcular_tea(
                    capex_eur_kwh=capex_kwh,
                    capacidade_kwh=max(float(capacidade_pack_kwh), 0.1),
                    custo_eletricidade_eur_kwh=max(float(custo_eletr), 0.0),
                    degradacao_anual_pct=max(float(degradacao_anual_pct), 0.0),
                    ciclos_por_dia=max(float(ciclos_por_dia), 0.0)
                )
            except Exception as tea_err:
                df_tea = pd.DataFrame({
                    "Indicador": ["TEA indisponível para esta combinação"],
                    "Valor": [_texto_erro(tea_err)]
                })
                st.warning("⚠️ A análise TEA encontrou uma condição numérica inválida; os restantes resultados continuam disponíveis.")
            st.caption(
                f"Capacidade do pack: {capacidade_pack_kwh:.2f} kWh · "
                f"Degradação anual equivalente: {degradacao_anual_pct:.2f} %/ano · "
                f"{ciclos_por_dia:.2f} ciclos/dia (assumindo {ciclos_por_ano} ciclos/ano)"
            )
            st.dataframe(df_tea, use_container_width=True)

            st.markdown("#### Sensibilidade TEA — Tornado")
            sens = calcular_sensibilidade_tea(capex_kwh, custo_eletr, capacidade_pack_kwh,
                                              degradacao_anual_pct, ciclos_por_dia, spread_arbitragem)
            st.dataframe(sens, use_container_width=True)
            if _plotly_disponivel():
                fig_t = go.Figure()
                for _,r in sens.iterrows():
                    fig_t.add_trace(go.Bar(y=[r["Parâmetro"]], x=[r["Variação baixa (-20%)"]], orientation="h", name="-20%"))
                    fig_t.add_trace(go.Bar(y=[r["Parâmetro"]], x=[r["Variação alta (+20%)"]], orientation="h", name="+20%"))
                fig_t.update_layout(title="Análise de Sensibilidade TEA (desvio face ao caso base)",
                                    barmode="relative", xaxis_title="Δ LCOS proxy [€/kWh]")
                _mostrar_plotly(fig_t)

            st.markdown("#### Valor de 2ª vida — EV → armazenamento estacionário")
            df_2vida=calcular_valor_segunda_vida(capacidade_pack_kwh,soh_final,capex_kwh,custo_eletr,spread_arbitragem,anos_segunda_vida)
            st.dataframe(df_2vida,use_container_width=True)
            st.caption("Modelo indicativo de segunda vida; o valor económico real depende de mercado, logística, teste de SOH e custos de recondicionamento.")
        else:
            st.warning("⚠️ O módulo `analise_economica.py` não pôde ser carregado.")
            if TEA_IMPORT_ERROR is not None:
                st.caption(f"Detalhe técnico: {_texto_erro(TEA_IMPORT_ERROR)}")

            st.markdown("#### Sensibilidade TEA — Tornado")
            sens = calcular_sensibilidade_tea(capex_kwh, custo_eletr, capacidade_pack_kwh,
                                              degradacao_anual_pct if 'degradacao_anual_pct' in locals() else 0.0,
                                              ciclos_por_dia if 'ciclos_por_dia' in locals() else 1.0, spread_arbitragem)
            st.dataframe(sens, use_container_width=True)
            st.markdown("#### Valor de 2ª vida — EV → armazenamento estacionário")
            st.dataframe(calcular_valor_segunda_vida(capacidade_pack_kwh,soh_final,capex_kwh,custo_eletr,spread_arbitragem,anos_segunda_vida),use_container_width=True)

    with tab_lca:
        st.markdown("#### Impacto do Ciclo de Vida (Módulo `analise_ambiental.py`)")
        if calcular_lca_bateria is not None:
            try:
                df_lca, pegada = calcular_lca_bateria(
                    capacidade_kwh=max(float(capacidade_pack_kwh), 0.1),
                    massa_kg=max(float(massa_pack_kg), 0.0),
                    quimica=quimica_tag,
                    vida_util_km=max(float(distancia_km), 0.0),
                    consumo_kwh_km=max(float(consumo_kwh_km), 0.0),
                    aplicacao_veicular=aplicacao_veicular
                )
                st.metric("Pegada de Carbono Específica", f"{float(pegada):.3g} kg CO2eq / kWh")
                cn = _carbono_nivelado(
                    float(pegada) * max(float(capacidade_pack_kwh), 0.1),
                    max(float(capacidade_pack_kwh), 0.1),
                    float(soh_final), 0.8, 0.9, max(int(num_ciclos), 1)
                )
                st.metric("Carbono Nivelado", f"{cn:.3g} kg CO2eq / MWh entregue")
                st.dataframe(df_lca, use_container_width=True)
            except Exception as lca_err:
                st.warning("⚠️ A análise LCA não conseguiu avaliar esta combinação, mas a simulação e a exportação permanecem disponíveis.")
                st.dataframe(pd.DataFrame({
                    "Indicador": ["LCA indisponível para esta combinação"],
                    "Detalhe": [_texto_erro(lca_err)]
                }), use_container_width=True)
            if quimica_tag == "Chumbo-Ácido" and aplicacao_veicular:
                st.info(
                    "ℹ️ Selecionaste 'Veicular (EV)', mas para Chumbo-Ácido o módulo de "
                    "LCA aplica sempre o perfil estacionário (3000 ciclos completos)."
                )
        else:
            st.warning("⚠️ O módulo `analise_ambiental.py` não pôde ser carregado.")
            if LCA_IMPORT_ERROR is not None:
                st.caption(f"Detalhe técnico: {_texto_erro(LCA_IMPORT_ERROR)}")

        st.markdown("#### Indicadores ambientais adicionais")
        st.dataframe(indicadores_lca_avancados(capacidade_pack_kwh,massa_pack_kg,quimica_tag),use_container_width=True)
        st.caption("Água e ecotoxicidade são apresentados como screening quando não existe inventário LCIA no módulo externo. Isto evita apresentar proxies como resultados ISO 14040 certificados.")

    with tab_dados:
        st.subheader("Resumo por Ciclo")
        st.dataframe(df_resumo, use_container_width=True)

        st.subheader("Série Temporal Contínua (Sanitizada)")
        st.dataframe(df_series, use_container_width=True)

        st.markdown("#### Comparação multiquímica")
        df_multi=comparar_multiquimica(capacidade_pack_kwh,massa_pack_kg,capex_kwh,custo_eletr,ciclos_por_ano,num_ciclos)
        st.dataframe(df_multi,use_container_width=True)
        if _plotly_disponivel() and not df_multi.empty:
            fig_multi=go.Figure()
            if "SOH final [%]" in df_multi:
                fig_multi.add_trace(go.Bar(x=df_multi["Química"],y=df_multi["SOH final [%]"],name="SOH final [%]"))
            if "Pegada carbono [kg CO2eq/kWh]" in df_multi:
                fig_multi.add_trace(go.Bar(x=df_multi["Química"],y=df_multi["Pegada carbono [kg CO2eq/kWh]"],name="CO2eq/kWh"))
            fig_multi.update_layout(title="Comparação NMC vs LFP vs NCA vs Chumbo-Ácido",barmode="group")
            _mostrar_plotly(fig_multi)

        csv_series = df_series.to_csv(index=False).encode('utf-8')
        metadata_export = {
            "quimica": tecnologia,
            "quimica_tag": quimica_tag,
            "modo_simulacao_pedido": modo_simulacao,
            "modo_simulacao_efetivo": metadata.get("modo_efetivo", modo_simulacao),
            "taxa_carga_C": _safe_float(taxa_carga),
            "taxa_descarga_C": _safe_float(taxa_descarga),
            "taxa_carga_efetiva_C": _safe_float(metadata.get("taxa_carga_efetiva", taxa_carga)),
            "taxa_descarga_efetiva_C": _safe_float(metadata.get("taxa_descarga_efetiva", taxa_descarga)),
            "numero_ciclos_pedido": int(num_ciclos),
            "numero_ciclos_obtidos": int(ciclos_obtidos),
            "temperatura_ambiente_C": _safe_float(temp_amb_c),
            "h_arrefecimento_W_m2K": _safe_float(h_cooling),
            "numero_celulas_pack": int(num_celulas_pack),
            "massa_por_celula_kg": _safe_float(massa_por_celula_kg),
            "capacidade_pack_kWh": _safe_float(capacidade_pack_kwh),
            "soh_final_pct": _safe_float(soh_final),
            "fallback_ativado": bool(metadata.get("fallback",False)),
        }
        json_metadata=json.dumps(metadata_export,ensure_ascii=False,indent=2).encode("utf-8")
        col_a,col_b=st.columns(2)
        with col_a:
            st.download_button(
                label="Descarregar Séries Temporais (CSV Limpo)",
                data=csv_series,
                file_name=f"series_temporais_{quimica_tag.lower()}_{num_ciclos}ciclos.csv",
                mime="text/csv"
            )
        with col_b:
            st.download_button(
                label="Descarregar Metadados (JSON)",
                data=json_metadata,
                file_name=f"metadados_{quimica_tag.lower()}_{num_ciclos}ciclos.json",
                mime="application/json"
            )
