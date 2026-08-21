import pybamm

# 1. Carregar o conjunto de parâmetros de Chen (2020)
parameter_values = pybamm.ParameterValues("Chen2020")

# 2. Consultar parâmetros da célula (com o nome do parâmetro corrigido)
print(f"Capacidade Nominal: {parameter_values['Nominal cell capacity [A.h]']} Ah")
print(f"Raio do Ânodo: {parameter_values['Negative particle radius [m]']} m")
print(f"Tensão Máxima: {parameter_values['Upper voltage cut-off [V]']} V")

# 3. Modificar a temperatura ambiente inicial para 25 °C (298.15 K)
parameter_values.update({"Ambient temperature [K]": 298.15})

# 4. Criar o modelo DFN e associar os parâmetros
model = pybamm.lithium_ion.DFN()
sim = pybamm.Simulation(model, parameter_values=parameter_values)

# 5. Executar a simulação de 1 hora (3600 segundos) e gerar o gráfico
sim.solve([0, 3600])
sim.plot()