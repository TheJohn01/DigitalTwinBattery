import pybamm
import matplotlib.pyplot as plt

# 1. Configurar o modelo DFN ativando as opções Térmica e de SEI
options = {
    "thermal": "lumped",                      # Modelo térmico concentrado (variação de temperatura)
    "SEI": "solvent-diffusion limited"        # Crescimento de SEI limitado por difusão
}
model = pybamm.lithium_ion.DFN(options=options)

# 2. Carregar os parâmetros da célula Chen (2020)
parameter_values = pybamm.ParameterValues("Chen2020")

# 3. Criar um protocolo de teste (Descarga e Carga rápidas a 2C)
experiment = pybamm.Experiment([
    "Discharge at 2C until 2.5 V",
    "Rest for 10 minutes",
    "Charge at 2C until 4.2 V",
    "Hold at 4.2 V until C/20"
])

# 4. Executar a simulação
sim = pybamm.Simulation(model, parameter_values=parameter_values, experiment=experiment)
solution = sim.solve()

# 5. Extrair variáveis chave (chave corrigida para o elétrodo negativo)
tempo_min = solution["Time [min]"].entries
temp_celsius = solution["X-averaged cell temperature [C]"].entries
sei_espessura = solution["X-averaged negative SEI thickness [m]"].entries

# 6. Plotar gráfico duplo (Temperatura e Espessura da SEI ao longo do tempo)
fig, ax1 = plt.subplots(figsize=(9, 5))

color = 'tab:red'
ax1.set_xlabel('Tempo [min]')
ax1.set_ylabel('Temperatura da Célula [°C]', color=color)
ax1.plot(tempo_min, temp_celsius, color=color, linewidth=2, label="Temperatura")
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(True)

ax2 = ax1.twinx()  
color = 'tab:blue'
ax2.set_ylabel('Espessura da SEI no Ânodo [m]', color=color)
ax2.plot(tempo_min, sei_espessura, color=color, linewidth=2, linestyle="--", label="Espessura SEI")
ax2.tick_params(axis='y', labelcolor=color)

plt.title("Fase 3: Acoplamento Térmico e Evolução da Camada SEI (Ânodo)")
fig.tight_layout()
plt.show()

# 7. Inspecionar visualmente no Dashboard nativo do PyBaMM
sim.plot([
    "Terminal voltage [V]",
    "Current [A]",
    "X-averaged cell temperature [C]",
    "X-averaged negative SEI thickness [m]"
])
