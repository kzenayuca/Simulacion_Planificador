import psutil
import time
import random

class Proceso:
    def __init__(self, pid, nombre, cpu_time, arrival_time, remaining_time, cpu_id, priority=5):
        self.pid = pid
        self.nombre = nombre
        self.cpu_time = cpu_time
        self.burst_time = cpu_time 
        self.arrival_time = arrival_time
        self.remaining_time = remaining_time
        self.cpu_id = cpu_id
        self.priority = priority

    def __repr__(self):
        return (f"Proceso(PID={self.pid}, Nombre={self.nombre}, "
                f"CPU Time={self.cpu_time}, Arrival Time={self.arrival_time}, "
                f"Remaining Time={self.remaining_time}, CPU={self.cpu_id}, Priority={self.priority})")