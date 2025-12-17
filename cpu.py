import time
from proceso import Proceso

class CPU:
    def __init__(self, id):
        self.id = id
        self.procesos = []  # Cola de procesos asignados
        self.algorithm = "FCFS"  # Algoritmo por defecto
        self.quantum = None  # Quantum solo aplicable a Round Robin

    def limpiar_procesos(self):
        self.procesos = []

    def asignar_proceso(self, proceso):
        self.procesos.append(proceso)

    def ejecutar_algoritmo(self):

        if self.algorithm == "SJF":
            self.procesos.sort(key=lambda p: p.cpu_time)  # ordena por tiempo de CPU más corto

        elif self.algorithm == "Round Robin" and self.quantum is not None:
            # Convertir la lista de procesos en segmentos según quantum (solo para mostrar)
            self.procesos = self.round_robin_simulation(self.procesos, self.quantum)

        elif self.algorithm == "FCFS":
            self.procesos = self.procesos

    def round_robin_simulation(self, procesos, quantum):
        cola = procesos[:] 
        resultado = []
        tiempo_restante = {p.pid: p.cpu_time for p in procesos}  # dict {pid -> tiempo que aun necesita}

        while cola:
            proceso = cola.pop(0)  # saca primer proceso

            if tiempo_restante[proceso.pid] > quantum:
                # proceso tiene más tiempo que el quantum!!!!!!!!!!!!!
                nuevo_segmento = Proceso(
                    proceso.pid, proceso.nombre, quantum,
                    proceso.arrival_time, tiempo_restante[proceso.pid] - quantum, proceso.cpu_id, getattr(proceso, 'priority', 5)
                )
                resultado.append(nuevo_segmento)
                tiempo_restante[proceso.pid] -= quantum
                cola.append(proceso)  # Reinsertar el proceso al final de la cola 
            else:
                #  proceso tiene menos tiempo que el quantum o termina
                nuevo_segmento = Proceso(
                    proceso.pid, proceso.nombre, tiempo_restante[proceso.pid],
                    proceso.arrival_time, 0, proceso.cpu_id, getattr(proceso, 'priority', 5)
                )
                resultado.append(nuevo_segmento)
                tiempo_restante[proceso.pid] = 0  # El proceso ha terminado

        return resultado

    def obtener_cola_procesos(self):
        return [f"PID: {p.pid}, Nombre: {p.nombre}, CPU Time: {p.cpu_time}, Priority: {getattr(p,'priority', '-') }" for p in self.procesos]

    # devuelve los procesos directamente
    def get_cola_procesos(self):
        return self.procesos