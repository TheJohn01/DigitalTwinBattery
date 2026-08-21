# Ficheiro de única fonte de verdade (single source of truth) para a
# física eletroquímica, parâmetros por química e comparação multiquímica.
# O app.py importa estas funções em vez de as redefinir, garantindo que
# a simulação standalone e o dashboard nunca divergem.

try:
    import pybamm
except Exception:
    # Mantém o módulo importável mesmo sem PyBaMM; as funções que usam
    # pybamm levantam um erro claro quando invocadas.
    pybamm = None

import numpy as np
import pandas as pd


# =====================================================================
# 1. Catálogos e lookup partilhados
# =====================================================================
quimicas_disponiveis = {
    "NMC/Grafite (Chen 2020)": "Chen2020",
    "LFP/Grafite (Prada 2013)": "Prada2013",
    "NCA/Grafite (Ai 2020)": "Ai2020",
    "Chumbo-Ácido (Sulzer 2019)": "Sulzer2019",
}

TENSOES_NOMINAIS = {
    "NMC/Grafite (Chen 2020)": 3.7,
    "LFP/Grafite (Prada 2013)": 3.2,
    "NCA/Grafite (Ai 2020)": 3.6,
    "Chumbo-Ácido (Sulzer 2019)": 2.0,
}

CAPEX_BASE_EUR_KWH = {"NMC": 125.0, "LFP": 95.0, "NCA": 130.0, "Chumbo-Ácido": 75.0}
CARBONO_FABRICO_KG_CO2_KWH = {"NMC": 85.0, "LFP": 55.0, "NCA": 90.0, "Chumbo-Ácido": 45.0}
DEGRADACAO_QUIMICA = {
    "NMC": (0.000045, 0.000010, 0.000003),
    "LFP": (0.000025, 0.000006, 0.000002),
    "NCA": (0.000050, 0.000012, 0.000003),
    "Chumbo-Ácido": (0.000120, 0.000030, 0.000008),
}


def _quimica_curta(tag):
    t = str(tag)
    if t.startswith("NMC"):
        return "NMC"
    if t.startswith("LFP"):
        return "LFP"
    if t.startswith("NCA"):
        return "NCA"
    if "Chumbo" in t:
        return "Chumbo-Ácido"
    return t


def _capex_quimica(tag):
    return float(CAPEX_BASE_EUR_KWH.get(_quimica_curta(tag), 130.0))


def _safe_float(x, default=0.0):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _carbono_nivelado(co2_kg, capacidade_kwh, soh, dod=.8, eficiencia=.9, ciclos=1):
    try:
        e = (max(float(capacidade_kwh), 0) * max(float(dod), 0)
             * max(float(eficiencia), 0) * max(float(ciclos), 0) / 1000)
        return max(float(co2_kg), 0) / e if np.isfinite(e) and e > 1e-12 else 0.0
    except Exception:
        return 0.0


# =====================================================================
# 2. Construção de parâmetros e modelo (idêntico ao app.py)
# =====================================================================
def _normalizar_taxas(taxa_carga, taxa_descarga):
    c = float(np.clip(float(taxa_carga), 0.05, 4.0))
    d = float(np.clip(float(taxa_descarga), 0.05, 3.0))
    return c, d


def _parametros_quimica(tecnologia):
    if "NMC" in tecnologia:
        return {
            "parameter_set": "Chen2020",
            "v_min": 2.5, "v_max": 4.2, "v_nom": 3.7,
            "tag": "NMC", "sei": True, "capacidade_base_ah": 5.0,
        }
    if "LFP" in tecnologia:
        return {
            "parameter_set": "Prada2013",
            "v_min": 2.0, "v_max": 3.6, "v_nom": 3.2,
            "tag": "LFP", "sei": True, "capacidade_base_ah": 5.0,
        }
    if "NCA" in tecnologia:
        return {
            "parameter_set": "Ai2020",
            "v_min": 2.8, "v_max": 4.2, "v_nom": 3.6,
            "tag": "NCA", "sei": True, "capacidade_base_ah": 5.0,
        }
    return {
        "parameter_set": "Sulzer2019",
        "v_min": 1.75, "v_max": 2.4, "v_nom": 2.0,
        "tag": "Chumbo-Ácido", "sei": False, "capacidade_base_ah": 5.0,
    }


def _parametros_termicos(temp_amb_c, h_cooling):
    return {
        "Ambient temperature [K]": float(temp_amb_c) + 273.15,
        "Initial temperature [K]": float(temp_amb_c) + 273.15,
        "Reference temperature [K]": float(temp_amb_c) + 273.15,
        "Total heat transfer coefficient [W.m-2.K-1]": float(h_cooling),
        "Cell cooling surface area [m2]": 0.0053,
        "Cell volume [m3]": 2.4e-5,
        "Cell specific heat capacity [J.kg-1.K-1]": 1100.0,
        "Cell density [kg.m-3]": 2400.0,
        "Cell thermal conductivity [W.m-1.K-1]": 1.0,
        "Negative electrode density [kg.m-3]": 1650.0,
        "Positive electrode density [kg.m-3]": 3250.0,
        "Separator density [kg.m-3]": 1000.0,
        "Negative electrode specific heat capacity [J.kg-1.K-1]": 700.0,
        "Positive electrode specific heat capacity [J.kg-1.K-1]": 700.0,
        "Separator specific heat capacity [J.kg-1.K-1]": 700.0,
        "Negative current collector thickness [m]": 15e-6,
        "Positive current collector thickness [m]": 15e-6,
        "Negative current collector density [kg.m-3]": 8960.0,
        "Positive current collector density [kg.m-3]": 2700.0,
        "Negative current collector specific heat capacity [J.kg-1.K-1]": 385.0,
        "Positive current collector specific heat capacity [J.kg-1.K-1]": 897.0,
        "Negative current collector thermal conductivity [W.m-1.K-1]": 398.0,
        "Positive current collector thermal conductivity [W.m-1.K-1]": 237.0,
        "Negative current collector conductivity [S.m-1]": 5.84e7,
        "Positive current collector conductivity [S.m-1]": 3.55e7,
    }


def _parametros_sei():
    return {
        "Initial SEI thickness [m]": 5e-9,
        "Initial inner SEI thickness [m]": 2.5e-9,
        "Initial outer SEI thickness [m]": 2.5e-9,
        "SEI solvent diffusivity [m2.s-1]": 5.0e-17,
        "SEI molar volume [m3.mol-1]": 9.58e-5,
        "SEI density [kg.m-3]": 1690.0,
        "SEI resistivity [Ohm.m]": 2.0e5,
        "SEI growth activation energy [J.mol-1]": 0.0,
        "SEI open-circuit potential [V]": 0.4,
        "Ratio of lithium moles to SEI moles": 2.0,
    }


def _construir_experiencia(taxa_carga, taxa_descarga, p):
    cc = max(float(taxa_carga), 0.05)
    cd = max(float(taxa_descarga), 0.05)
    return (
        f"Discharge at {cd:g}C for 6 hours or until {p['v_min']:.3f} V",
        "Rest for 5 minutes",
        f"Charge at {cc:g}C for 6 hours or until {p['v_max']:.3f} V",
        f"Hold at {p['v_max']:.3f} V until C/20",
        "Rest for 5 minutes",
    )


def _solver_robusto():
    if pybamm is None:
        return None
    try:
        return pybamm.IDAKLUSolver(rtol=1e-6, atol=1e-8)
    except Exception:
        try:
            return pybamm.CasadiSolver(mode="safe", rtol=1e-6, atol=1e-8)
        except Exception:
            return None


def _criar_modelo_e_parametros(modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                               temp_amb_c, h_cooling, variante):
    """Cria combinações progressivamente mais conservadoras.

    Variante 0: configuração pedida (thermal lumped + SEI).
    Variante 1: mesma física, sem SEI.
    Variante 2: mesma química, isotérmica.
    Variante 3: SPMe isotérmico (fallback para DFN).
    Para chumbo-ácido são usadas apenas opções válidas do modelo de chumbo.
    """
    if pybamm is None:
        raise RuntimeError("PyBaMM não está instalado no ambiente.")

    p = _parametros_quimica(tecnologia)
    carga, descarga = _normalizar_taxas(taxa_carga, taxa_descarga)

    if p["tag"] == "Chumbo-Ácido":
        model = pybamm.lead_acid.LOQS(options={"thermal": "isothermal"})
        pv = pybamm.ParameterValues(p["parameter_set"])
        pv.update({
            "Ambient temperature [K]": float(temp_amb_c) + 273.15,
            "Initial temperature [K]": float(temp_amb_c) + 273.15,
        }, check_already_exists=False)
        carga = min(carga, 0.5)
        descarga = min(descarga, 0.5)
        return model, pv, carga, descarga, False, p

    usar_sei = p["sei"] and variante == 0
    termico = variante < 2
    nome_modelo = "SPMe" if ("SPMe" in modo_simulacao or variante >= 3) else "DFN"

    options = {"thermal": "lumped" if termico else "isothermal"}
    if usar_sei:
        options["SEI"] = "solvent-diffusion limited"

    if nome_modelo == "SPMe":
        model = pybamm.lithium_ion.SPMe(options=options)
    else:
        model = pybamm.lithium_ion.DFN(options=options)

    pv = pybamm.ParameterValues(p["parameter_set"])
    pv.update(_parametros_termicos(temp_amb_c, h_cooling), check_already_exists=False)
    if usar_sei:
        pv.update(_parametros_sei(), check_already_exists=False)

    return model, pv, carga, descarga, usar_sei, p


def _texto_erro(err):
    try:
        return str(err).strip().replace("\\x1b", "")[:1000]
    except Exception:
        return "Erro de solver não especificado."


def _executar_pybamm(modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                     num_ciclos, temp_amb_c, h_cooling):
    """Tenta a configuração pedida e, em caso de falha numérica, simplifica
    apenas a física que causou a falha. Nenhuma funcionalidade da UI é removida."""
    erros = []
    p = _parametros_quimica(tecnologia)

    variantes = [0, 1, 2]
    if "DFN" in modo_simulacao and p["tag"] != "Chumbo-Ácido":
        variantes.append(3)

    for variante in variantes:
        try:
            model, pv, carga, descarga, tem_sei, p2 = _criar_modelo_e_parametros(
                modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                temp_amb_c, h_cooling, variante
            )
            passo = _construir_experiencia(carga, descarga, p2)

            experiment = pybamm.Experiment([passo] * (int(num_ciclos) + 1))
            solver = _solver_robusto()
            kwargs = {}
            if solver is not None:
                kwargs["solver"] = solver
            try:
                solution = pybamm.Simulation(
                    model, parameter_values=pv, experiment=experiment
                ).solve(**kwargs)
            except TypeError:
                solution = pybamm.Simulation(
                    model, parameter_values=pv, experiment=experiment
                ).solve()

            meta = {
                "tem_sei": bool(tem_sei),
                "quimica_tag": p2["tag"],
                "modo_efetivo": (
                    "SPMe (fallback)" if variante >= 3 else
                    ("isotérmico (fallback)" if variante >= 2 else
                     ("sem SEI (fallback)" if variante == 1 else modo_simulacao))
                ),
                "fallback": variante != 0,
                "taxa_carga_efetiva": carga,
                "taxa_descarga_efetiva": descarga,
                "mensagem_fallback": "; ".join(erros) if erros else "",
            }
            return solution, meta, None

        except Exception as err:
            erros.append(f"Tentativa {variante}: {_texto_erro(err)}")

    return None, None, " | ".join(erros[-3:])


def executar_simulacao(modo_simulacao, tecnologia, taxa_carga=1.5, taxa_descarga=1.5,
                       num_ciclos=10, temp_amb_c=25.0, h_cooling=10.0):
    """Executa a simulação física pedida (mesma lógica de variante 0 a 3)."""
    return _executar_pybamm(modo_simulacao, tecnologia, taxa_carga, taxa_descarga,
                            num_ciclos, temp_amb_c, h_cooling)


# =====================================================================
# 3. Comparação multiquímica (consumida pelo app.py)
# =====================================================================
def comparar_quimicas(capacidade_pack_kwh, massa_pack_kg, capex, eletricidade,
                      ciclos_ano, num_ciclos, taxa_descarga=1.5, temp_amb_c=25.0):
    """Modelo determinístico de screening com os mesmos indicadores do app.py.

    Substitui a lógica de fallback de comparar_multiquimica e é a única
    implementação importada pelo dashboard.
    """
    nomes = ["NMC", "LFP", "NCA", "Chumbo-Ácido"]
    base_soh = {"NMC": 98.0, "LFP": 99.0, "NCA": 97.5, "Chumbo-Ácido": 92.0}
    carbono = {"NMC": 85.0, "LFP": 55.0, "NCA": 90.0, "Chumbo-Ácido": 45.0}
    rows = []
    for q in nomes:
        base = base_soh[q]
        b, c, t = DEGRADACAO_QUIMICA[q]
        ciclos = max(int(num_ciclos), 1)
        cd = max(float(taxa_descarga), 0.1)
        ta = max(float(temp_amb_c), 0.0)
        stress = b + c * cd + t * max(ta - 25.0, 0.0)
        if q == "Chumbo-Ácido":
            stress *= 1.0 + 0.01 * max(ciclos - 100, 0) / 100.0
        exp = float(np.exp(-stress * ciclos))
        soh = base * exp + 100.0 * (1.0 - exp)
        custo = max(_capex_quimica(q) * max(capacidade_pack_kwh, .1), 0)
        rows.append({
            "Química": q,
            "SOH final [%]": round(soh, 2),
            "Custo pack indicativo [€]": round(custo, 2),
            "CAPEX [€/kWh]": _capex_quimica(q),
            "Pegada carbono [kg CO2eq/kWh]": carbono[q],
            "Carbono nivelado [kg CO2eq/MWh]": round(
                _carbono_nivelado(carbono[q] * max(capacidade_pack_kwh, .1),
                                  max(capacidade_pack_kwh, .1), soh, .8, .9,
                                  max(int(num_ciclos), 1)), 2),
            "Capacidade [kWh]": round(max(capacidade_pack_kwh, .1), 3),
        })
    return pd.DataFrame(rows)


comparacao_multiquimica = comparar_quimicas
executar_comparacao = comparar_quimicas


if __name__ == "__main__":
    escolha = "LFP/Grafite (Prada 2013)"
    solution, meta, err = executar_simulacao(
        "DFN (Físico Detalhado - Alta Precisão)",
        escolha,
        taxa_carga=1.5,
        taxa_descarga=1.5,
        num_ciclos=10,
        temp_amb_c=25.0,
        h_cooling=10.0,
    )
    if err or solution is None:
        print("Falha na simulação:", err)
    else:
        print(f"Química: {escolha} ({meta['quimica_tag']})")
        print(f"Modo efetivo: {meta['modo_efetivo']} | SEI: {meta['tem_sei']}")
        print(f"Taxas efetivas -> carga: {meta['taxa_carga_efetiva']} C | descarga: {meta['taxa_descarga_efetiva']} C")
        print(f"Ciclos simulados: {len(solution.cycles) - 1}")
        solution.plot()
