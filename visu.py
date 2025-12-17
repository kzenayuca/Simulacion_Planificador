import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import threading
import time
from random import uniform, randint
from datetime import datetime

from proceso import Proceso
from cpu import CPU


class VisualizadorProcesos:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador de Procesos - Sistema de Planificación")
        self.root.geometry("1400x900")

        # Colores modernos
        self.colors = {
            'bg_primary': '#f5f7fa',
            'bg_header': "#52576d",
            'bg_button': "#585d75",
            'bg_button_hover': "#7e83a5",
            'text_primary': '#2d3748',
            'text_secondary': '#718096',
            'accent': "#64c488",
            'danger': "#be5858",
            'warning': '#ed8936',
            'info': "#5881a3"
        }

        self.root.configure(bg=self.colors['bg_primary'])

        self.procesos = []
        self.assigned_pids = set()
        self.cpus = [CPU(id=i + 1) for i in range(4)]

        # Colas multinivel (globales)
        self.high_queue = []  # procesos de máxima prioridad (se procesan con RR)
        self.low_queue = []   # procesos de mínima prioridad (se procesan con FCFS)
        self.priority_threshold = 5  # valor por encima o igual => alta prioridad
        self.default_rr_quantum = 1.0

        # Interfaz
        self._create_header()
        self._create_metrics_panel()
        self._create_table()
        self._create_button_panel()

        # Estado de simulación
        self.sim_thread = None
        self.sim_running = False
        self.sim_lock = threading.Lock()
        self.completed_info = {}

    def _create_header(self):
        header_frame = tk.Frame(self.root, bg=self.colors['bg_header'], height=30)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)

    def _create_metrics_panel(self):
        metrics_frame = tk.Frame(self.root, bg=self.colors['bg_primary'])
        metrics_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        # Tarjetas de métricas
        self.metric_cpus = self._create_metric_card(metrics_frame, "CPUs Disponibles", str(len(self.cpus)), self.colors['info'])
        self.metric_processes = self._create_metric_card(metrics_frame, "Procesos Activos", "0", self.colors['accent'])
        self.metric_completed = self._create_metric_card(metrics_frame, "Completados", "0", self.colors['warning'])
        self.metric_status = self._create_metric_card(metrics_frame, "Estado Sistema", "Listo", self.colors['accent'])

    def _create_metric_card(self, parent, title, value, color):
        """Crear tarjeta de métrica individual"""
        card = tk.Frame(parent, bg='white', relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Borde de color en la parte superior
        top_border = tk.Frame(card, bg=color, height=4)
        top_border.pack(fill=tk.X)

        tk.Label(
            card,
            text=title,
            font=('Segoe UI', 10),
            bg='white',
            fg=self.colors['text_secondary']
        ).pack(pady=(10, 2))

        value_label = tk.Label(
            card,
            text=value,
            font=('Segoe UI', 20, 'bold'),
            bg='white',
            fg=self.colors['text_primary']
        )
        value_label.pack(pady=(0, 10))

        return value_label

    def _create_table(self):
        """Crear tabla de procesos con diseño mejorado"""
        table_frame = tk.Frame(self.root, bg=self.colors['bg_primary'])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Configurar colores del Treeview
        style.configure(
            "Custom.Treeview",
            background='white',
            foreground=self.colors['text_primary'],
            rowheight=35,
            fieldbackground='white',
            borderwidth=0,
            font=('Segoe UI', 10)
        )

        style.configure(
            "Custom.Treeview.Heading",
            background=self.colors['bg_header'],
            foreground='white',
            relief='flat',
            font=('Segoe UI', 11, 'bold')
        )

        style.map('Custom.Treeview', background=[('selected', self.colors['bg_button'])])
        style.map('Custom.Treeview.Heading', background=[('active', '#5568d3')])

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview
        self.tree = ttk.Treeview(
            table_frame,
            columns=("PID", "Nombre", "CPU Time", "Arrival Time", "Remaining Time", "Priority"),
            show="headings",
            style="Custom.Treeview",
            yscrollcommand=scrollbar.set
        )

        scrollbar.config(command=self.tree.yview)

        # Configurar columnas
        columns_config = {
            "PID": 80,
            "Nombre": 250,
            "CPU Time": 120,
            "Arrival Time": 200,
            "Remaining Time": 140,
            "Priority": 80
        }

        for col, width in columns_config.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor='center' if col == "PID" else 'w')

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Tags para colores alternados
        self.tree.tag_configure('oddrow', background='#f8f9fa')
        self.tree.tag_configure('evenrow', background='white')

    def _create_button_panel(self):
        """Panel de botones mejorado"""
        btn_frame = tk.Frame(self.root, bg=self.colors['bg_primary'])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        buttons = [
            ("➕ Agregar Proceso", self.agregar_proceso, self.colors['bg_button']),
            ("📥 Importar Procesos", self.importar_procesos, self.colors['accent']),
            ("🗑️ Eliminar Proceso", self.eliminar_proceso, self.colors['danger']),
            ("💻 Asignar a CPUs", self.asignar_procesos_a_cpus, self.colors['warning']),
            ("⚙️ Configurar CPUs", self.configurar_cpus, self.colors['info']),
            ("▶️ Simular en Vivo", self.abrir_simulador_en_vivo, '#38ef7d')
        ]

        for i, (text, command, color) in enumerate(buttons):
            btn = tk.Button(
                btn_frame,
                text=text,
                command=command,
                bg=color,
                fg='white',
                font=('Segoe UI', 11, 'bold'),
                relief=tk.FLAT,
                cursor='hand2',
                padx=20,
                pady=12,
                borderwidth=0
            )
            btn.grid(row=0, column=i, padx=5, sticky='ew')

            # Efectos hover
            btn.bind('<Enter>', lambda e, b=btn, c=color: self._on_button_hover(b, c))
            btn.bind('<Leave>', lambda e, b=btn, c=color: self._on_button_leave(b, c))

        # Configurar peso de columnas
        for i in range(len(buttons)):
            btn_frame.columnconfigure(i, weight=1)

    def _on_button_hover(self, button, color):
        """Efecto hover en botones"""
        button.configure(bg=self._darken_color(color))

    def _on_button_leave(self, button, color):
        """Restaurar color original"""
        button.configure(bg=color)

    def _darken_color(self, hex_color):
        """Oscurecer un color hexadecimal"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f'#{r:02x}{g:02x}{b:02x}'

    def actualizar_tabla(self):
        """Actualizar tabla con colores alternados"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, proceso in enumerate(self.procesos):
            arrival = datetime.fromtimestamp(proceso.arrival_time).strftime("%Y-%m-%d %H:%M:%S") if proceso.arrival_time else "0"
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", "end", values=(
                proceso.pid,
                proceso.nombre,
                f"{proceso.cpu_time:.2f}",
                arrival,
                f"{proceso.remaining_time:.2f}",
                getattr(proceso, 'priority', '-')
            ), tags=(tag,))

        # Actualizar métricas
        self.metric_processes.config(text=str(len(self.procesos)))
        self.metric_completed.config(text=str(len(self.completed_info)))

    def agregar_proceso(self):
        ventana_agregar = tk.Toplevel(self.root)
        ventana_agregar.title("Agregar Proceso")
        ventana_agregar.geometry("450x500")
        ventana_agregar.configure(bg='white')

        # Header
        header = tk.Frame(ventana_agregar, bg=self.colors['bg_header'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="➕ Nuevo Proceso", font=('Segoe UI', 16, 'bold'),
            bg=self.colors['bg_header'], fg='white'
        ).pack(pady=15)

        content = tk.Frame(ventana_agregar, bg='white')
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        if self.procesos:
            next_pid = max(p.pid for p in self.procesos) + 1
        else:
            next_pid = 1
            
        default_name = f"Proceso_{next_pid}"
        default_cpu = f"{uniform(2.0, 8.0):.1f}" # Formato string con 1 decimal
        default_prio = str(randint(0, 10))

        print(f"DEBUG: Calculados -> PID:{next_pid}, Name:{default_name}, CPU:{default_cpu}")

        fields = [
            ("PID:", "entry_pid", str(next_pid)),
            ("Nombre:", "entry_nombre", default_name),
            ("CPU Time (s):", "entry_cpu_time", default_cpu),
            ("Priority (0-10):", "entry_priority", default_prio)
        ]

        self.entry_widgets = {}

        # BUCLE DE CREACIÓN CON STRINGVAR
        for label_text, entry_name, default_val in fields:
            tk.Label(
                content, text=label_text, font=('Segoe UI', 11),
                bg='white', fg=self.colors['text_primary']
            ).pack(anchor='w', pady=(10, 2))

            # USAMOS STRINGVAR: Esto "ata" el valor al campo de texto fuertemente
            var_control = tk.StringVar(value=default_val)
            
            entry = tk.Entry(
                content, 
                textvariable=var_control,
                font=('Segoe UI', 11), 
                relief=tk.FLAT,
                bg='#f7fafc', 
                fg=self.colors['text_primary'],
                insertbackground=self.colors['bg_button']
            )
            entry.pack(fill=tk.X, ipady=8, pady=(0, 5))
            
            self.entry_widgets[entry_name] = entry

        def guardar_proceso():
            try:
                pid = int(self.entry_widgets['entry_pid'].get())
                nombre = self.entry_widgets['entry_nombre'].get()
                cpu_time = float(self.entry_widgets['entry_cpu_time'].get())
                priority = int(self.entry_widgets['entry_priority'].get())
                
                if any(p.pid == pid for p in self.procesos):
                    messagebox.showwarning("Error", f"El PID {pid} ya existe.")
                    return

                nuevo = Proceso(pid, nombre, cpu_time, time.time(), cpu_time, None, priority)
                self.procesos.append(nuevo)
                self.actualizar_tabla()
                ventana_agregar.destroy()
                print(f"DEBUG: Proceso {nombre} guardado correctamente.")
                
            except ValueError:
                messagebox.showerror("Error", "Revise que los números sean válidos.")

        btn_guardar = tk.Button(
            content, text="Guardar Proceso", command=guardar_proceso,
            bg=self.colors['accent'], fg='white', font=('Segoe UI', 11, 'bold'),
            relief=tk.FLAT, cursor='hand2', padx=20, pady=12
        )
        btn_guardar.pack(pady=20)
        
        ventana_agregar.bind('<Return>', lambda event: guardar_proceso())
        btn_guardar.focus_set()

    def importar_procesos(self):
        raw_procs = []
        try:
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'cpu_times']):
                try:
                    p.cpu_percent(interval=None) 
                    raw_procs.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error leyendo procesos: {e}")

        # 2. ORDENAR por uso de CPU (descendente)
        # Queremos ver los que están haciendo algo, no los que están en 0%
        # Usamos un valor por defecto 0.0 si no se puede leer
        raw_procs.sort(key=lambda p: p.info.get('cpu_percent') or 0.0, reverse=True)

        top_procs = raw_procs[:25]
        
        count = 0
        existing_pids = {p.pid for p in self.procesos}

        for p in top_procs:
            try:
                pid = p.info['pid']
                if pid in existing_pids:
                    continue
                
                nombre = p.info.get('name') or f"proc{pid}"
                
                # Calcular tiempo de ráfaga
                ct = p.info.get('cpu_times')
                if ct:
                    # Si el proceso real tiene tiempo acumulado, usamos una fracción
                    # para que no sea infinito en la simulación
                    raw_time = (ct.user + ct.system)
                    # Truco: Si es muy grande, lo limitamos a algo visible (ej. entre 2 y 8 seg)
                    if raw_time > 10:
                        cpu_time = uniform(4.0, 12.0)
                    else:
                        cpu_time = max(1.0, raw_time)
                else:
                    cpu_time = uniform(1.0, 5.0)

                arrival_time = self.sim_time if hasattr(self, 'sim_time') else 0.0
                priority = randint(0, 10)
                
                nuevo_proceso = Proceso(pid, nombre, cpu_time, arrival_time, cpu_time, None, priority)
                self.procesos.append(nuevo_proceso)
                existing_pids.add(pid)
                count += 1
                
            except Exception:
                continue

        self.actualizar_tabla()
        messagebox.showinfo("Importación Inteligente", f"Se importaron los {count} procesos más activos del sistema.") 

    def eliminar_proceso(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Debe seleccionar un proceso para eliminar.")
            return

        pid_seleccionado = int(self.tree.item(seleccion, 'values')[0])
        self.procesos = [p for p in self.procesos if p.pid != pid_seleccionado]
        for cpu in self.cpus:
            cpu.procesos = [p for p in cpu.procesos if p.pid != pid_seleccionado]
        self.assigned_pids.discard(pid_seleccionado)
        self.actualizar_tabla()
        messagebox.showinfo("Éxito", "Proceso eliminado correctamente")

    def asignar_procesos_a_cpus(self, silent=False): # <--- 1. Agregamos parámetro
        if not self.procesos:
            if not silent: # Solo mostrar error si es manual
                messagebox.showwarning("Advertencia", "No hay procesos para asignar.")
            return

        # 1) limpiar CPUs
        for cpu in self.cpus:
            cpu.limpiar_procesos()
        self.assigned_pids.clear()

        # 2) construir colas globales (Consideramos todos los procesos actuales)
        # Nota: Al reasignar, tomamos todos para redistribuir carga
        self.high_queue = [p for p in self.procesos if p.priority >= self.priority_threshold]
        self.high_queue.sort(key=lambda p: p.arrival_time)
        
        self.low_queue = [p for p in self.procesos if p.priority < self.priority_threshold]
        self.low_queue.sort(key=lambda p: p.arrival_time)

        # 3) asignar high priority (RR)
        cpu_count = len(self.cpus)
        idx = 0
        while self.high_queue:
            proceso = self.high_queue.pop(0)
            cpu = self.cpus[idx % cpu_count]
            cpu.asignar_proceso(proceso)
            
            cpu.algorithm = "Round Robin"
            if cpu.quantum is None:
                cpu.quantum = self.default_rr_quantum
            
            proceso.cpu_id = cpu.id
            self.assigned_pids.add(proceso.pid)
            idx += 1

        # 4) asignar low priority (FCFS)
        idx = 0
        while self.low_queue:
            proceso = self.low_queue.pop(0)
            cpu = self.cpus[idx % cpu_count]
            cpu.asignar_proceso(proceso)
            
            if cpu.algorithm != "Round Robin":
                cpu.algorithm = "FCFS"
            
            proceso.cpu_id = cpu.id
            self.assigned_pids.add(proceso.pid)
            idx += 1

        # --- 2. EL CAMBIO CLAVE ESTÁ AQUÍ ---
        if not silent:
            messagebox.showinfo("Asignación", "Procesos asignados a las CPUs correctamente.")

    def configurar_cpus(self):
        ventana_config = tk.Toplevel(self.root)
        ventana_config.title("Configurar CPUs")
        ventana_config.geometry("700x530")
        ventana_config.configure(bg='white')

        # Header
        header = tk.Frame(ventana_config, bg=self.colors['bg_header'], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="⚙️ Configuración de CPUs",
            font=('Segoe UI', 18, 'bold'),
            bg=self.colors['bg_header'],
            fg='white'
        ).pack(pady=18)

        content = tk.Frame(ventana_config, bg='white')
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        for cpu in self.cpus:
            frame_cpu = tk.Frame(content, bg='#f7fafc', relief=tk.FLAT, bd=1)
            frame_cpu.pack(pady=8, fill=tk.X, ipady=10, ipadx=10)

            tk.Label(
                frame_cpu,
                text=f"CPU {cpu.id}",
                font=('Segoe UI', 12, 'bold'),
                bg='#f7fafc',
                fg=self.colors['text_primary']
            ).grid(row=0, column=0, padx=15, sticky='w')

            tk.Label(
                frame_cpu,
                text="Algoritmo:",
                font=('Segoe UI', 10),
                bg='#f7fafc',
                fg=self.colors['text_secondary']
            ).grid(row=0, column=1, padx=10)

            btn_configs = [
                ("FCFS", lambda cpu_obj=cpu: self.configurar_algoritmo(cpu_obj, "FCFS", None)),
                ("SJF", lambda cpu_obj=cpu: self.configurar_algoritmo(cpu_obj, "SJF", None)),
                ("Round Robin", lambda cpu_obj=cpu: self.abrir_config_rr(cpu_obj)),
                ("Multinivel", lambda cpu_obj=cpu: self.configurar_algoritmo(cpu_obj, "Multinivel", None))
            ]

            for idx, (text, cmd) in enumerate(btn_configs):
                btn = tk.Button(
                    frame_cpu,
                    text=text,
                    command=cmd,
                    bg=self.colors['bg_button'],
                    fg='white',
                    font=('Segoe UI', 9, 'bold'),
                    relief=tk.FLAT,
                    cursor='hand2',
                    padx=15,
                    pady=8
                )
                btn.grid(row=0, column=2+idx, padx=5)

        # Controles globales de multinivel
        controls_frame = tk.Frame(ventana_config, bg='white')
        controls_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(controls_frame, text="Umbral prioridad (>=):", bg='white', fg=self.colors['text_primary']).grid(row=0, column=0, sticky='w')
        entry_thresh = tk.Entry(controls_frame, width=6)
        entry_thresh.insert(0, str(self.priority_threshold))
        entry_thresh.grid(row=0, column=1, padx=(5, 20))

        tk.Label(controls_frame, text="Default RR Quantum (s):", bg='white', fg=self.colors['text_primary']).grid(row=0, column=2, sticky='w')
        entry_q = tk.Entry(controls_frame, width=6)
        entry_q.insert(0, str(self.default_rr_quantum))
        entry_q.grid(row=0, column=3, padx=(5, 20))

        def guardar_configs():
            try:
                th = int(entry_thresh.get())
                qv = float(entry_q.get())
                self.priority_threshold = max(0, min(10, th))
                self.default_rr_quantum = max(0.01, qv)
                messagebox.showinfo("Configuración", "Parámetros actualizados")
            except ValueError:
                messagebox.showerror("Error", "Valores inválidos")

        tk.Button(ventana_config, text="Guardar", command=lambda: [guardar_configs(), ventana_config.destroy()], bg=self.colors['accent'], fg='white',
                  font=('Segoe UI', 11, 'bold'), relief=tk.FLAT, cursor='hand2', padx=20, pady=10).pack(pady=8)

    def configurar_algoritmo(self, cpu, algoritmo, quantum):
        cpu.algorithm = algoritmo
        cpu.quantum = quantum
        messagebox.showinfo("Configuración", f"CPU {cpu.id} configurada con {algoritmo}")

    def abrir_config_rr(self, cpu):
        ventana_rr = tk.Toplevel(self.root)
        ventana_rr.title(f"Configurar Quantum - CPU {cpu.id}")
        ventana_rr.geometry("400x290")
        ventana_rr.configure(bg='white')

        header = tk.Frame(ventana_rr, bg=self.colors['bg_header'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text=f"Quantum CPU {cpu.id}",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['bg_header'],
            fg='white'
        ).pack(pady=15)

        content = tk.Frame(ventana_rr, bg='white')
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        tk.Label(
            content,
            text="Ingrese el valor del quantum:",
            font=('Segoe UI', 11),
            bg='white',
            fg=self.colors['text_primary']
        ).pack(pady=10)

        entry_quantum = tk.Entry(
            content,
            font=('Segoe UI', 12),
            relief=tk.FLAT,
            bg='#f7fafc',
            justify='center'
        )
        entry_quantum.insert(0, str(cpu.quantum) if cpu.quantum is not None else str(self.default_rr_quantum))
        entry_quantum.pack(fill=tk.X, ipady=10, pady=10)

        def guardar_rr():
            try:
                quantum = float(entry_quantum.get())
                self.configurar_algoritmo(cpu, "Round Robin", quantum)
                ventana_rr.destroy()
            except ValueError:
                messagebox.showerror("Error", "El quantum debe ser un número válido.")

        tk.Button(
            content,
            text="Guardar",
            command=guardar_rr,
            bg=self.colors['accent'],
            fg='white',
            font=('Segoe UI', 11, 'bold'),
            relief=tk.FLAT,
            cursor='hand2',
            padx=30,
            pady=12
        ).pack(pady=15)

    def abrir_simulador_en_vivo(self):
        if self.sim_running:
            messagebox.showinfo("Simulación", "La simulación ya está en ejecución.")
            return

        self.sim_win = tk.Toplevel(self.root)
        self.sim_win.title("Simulación de Planificación en Vivo")
        self.sim_win.geometry("1400x1000")
        self.sim_win.configure(bg=self.colors['bg_primary'])

        # Header
        header = tk.Frame(self.sim_win, bg=self.colors['bg_header'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Simulación en Tiempo Real",
            font=('Segoe UI', 20, 'bold'),
            bg=self.colors['bg_header'],
            fg='white'
        ).pack(pady=20)

        # Layout principal
        main_container = tk.Frame(self.sim_win, bg=self.colors['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        left_frame = tk.Frame(main_container, bg='white', width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)

        right_frame = tk.Frame(main_container, bg='white')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Panel de CPUs
        self.cpu_frames = {}
        for cpu in self.cpus:
            f = tk.LabelFrame(
                left_frame,
                text=f"💻 CPU {cpu.id}",
                font=('Segoe UI', 11, 'bold'),
                bg='white',
                fg=self.colors['text_primary'],
                padx=10,
                pady=10
            )
            f.pack(fill=tk.X, padx=10, pady=8)

            lbl_running = tk.Label(
                f,
                text="Ejecutando: -",
                font=('Segoe UI', 10),
                bg='white',
                fg=self.colors['text_primary']
            )
            lbl_running.pack(anchor="w", pady=(0, 5))

            lst_queue = tk.Listbox(
                f,
                height=4,
                font=('Segoe UI', 9),
                bg='#f7fafc',
                relief=tk.FLAT
            )
            lst_queue.pack(fill=tk.X, pady=5)
            self.cpu_frames[cpu.id] = (lbl_running, lst_queue)

        # Métricas
        metrics_frame = tk.LabelFrame(
            left_frame,
            text="📊 Métricas",
            font=('Segoe UI', 11, 'bold'),
            bg='white',
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        metrics_frame.pack(fill=tk.X, padx=10, pady=8)

        self.avg_wait_label = tk.Label(
            metrics_frame,
            text="Espera promedio: 0.00s",
            font=('Segoe UI', 10),
            bg='white',
            fg=self.colors['text_primary']
        )
        self.avg_wait_label.pack(anchor="w", pady=2)

        self.completed_label = tk.Label(
            metrics_frame,
            text="Procesos completados: 0",
            font=('Segoe UI', 10),
            bg='white',
            fg=self.colors['text_primary']
        )
        self.completed_label.pack(anchor="w", pady=2)

        # Controles
        ctrl_frame = tk.Frame(left_frame, bg='white')
        ctrl_frame.pack(fill=tk.X, padx=10, pady=15)

        ctrl_buttons = [
            ("▶️ Iniciar", self.start_simulation, self.colors['accent']),
            ("⏸️ Pausar", self.pause_simulation, self.colors['warning']),
            ("⏹️ Detener", self.stop_simulation, self.colors['danger'])
        ]

        for text, cmd, color in ctrl_buttons:
            tk.Button(
                ctrl_frame,
                text=text,
                command=cmd,
                bg=color,
                fg='white',
                font=('Segoe UI', 10, 'bold'),
                relief=tk.FLAT,
                cursor='hand2',
                padx=15,
                pady=8
            ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Canvas Gantt
        gantt_header = tk.Frame(right_frame, bg=self.colors['bg_header'], height=50)
        gantt_header.pack(fill=tk.X)
        gantt_header.pack_propagate(False)
        tk.Label(
            gantt_header,
            text="📈 Diagrama de Gantt",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['bg_header'],
            fg='white'
        ).pack(pady=12)

        self.gantt_canvas = tk.Canvas(right_frame, bg='white')
        self.gantt_canvas.pack(fill=tk.BOTH, expand=True)

        self.gantt_segments = []
        self.sim_time = 0.0
        self.sim_tick = 0.1

        self.sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.sim_running = False
        self.sim_pause = True
        self.sim_thread.start()

        self._assign_new_processes()
        self._gui_update()

    def start_simulation(self):
        if not self.sim_thread.is_alive():
            return
        self.sim_pause = False
        self.sim_running = True
        self.metric_status.config(text="Ejecutando")

    def pause_simulation(self):
        self.sim_pause = True
        self.metric_status.config(text="Pausado")

    def stop_simulation(self):
        self.sim_running = False
        self.sim_pause = True
        self.metric_status.config(text="Detenido")

    def _assign_new_processes(self):
        # Detectar si hay procesos en la lista que no están en el set de asignados
        unassigned = [p for p in self.procesos if p.pid not in self.assigned_pids]
        
        if not unassigned:
            return

        # Llamamos a la asignación en modo SILENCIOSO para no interrumpir la simulación
        self.asignar_procesos_a_cpus(silent=True)

    def _simulation_loop(self):
        # Este hilo se encarga de la lógica----------- cualquier actualización de GUI se hace con root.after
        last_assign_check = time.time()
        while True:
            time.sleep(0.01)
            if not self.sim_running or self.sim_pause:
                time.sleep(0.1)
                continue

            with self.sim_lock:
                # Chequear procesos nuevos cada 0.5s
                if time.time() - last_assign_check > 0.5:
                    self._assign_new_processes()
                    last_assign_check = time.time()

                # Avanzar simulación por tick
                self.sim_time += self.sim_tick

                for cpu in self.cpus:
                    # Asegurar que la cola respete el algoritmo
                    if cpu.algorithm == "SJF":
                        cpu.procesos.sort(key=lambda p: p.remaining_time)

                    # Obtener proceso en ejecución (head of queue)
                    if not cpu.procesos:
                        continue

                    current = cpu.procesos[0]

                    # Determinar slice (considerar RR quantum)
                    slice_time = self.sim_tick
                    if cpu.algorithm == "Round Robin" and cpu.quantum:
                        if not hasattr(current, 'rr_used'):
                            current.rr_used = 0.0
                        remaining_quantum = cpu.quantum - current.rr_used
                        slice_time = min(slice_time, remaining_quantum)

                    # Ejecutar slice
                    executed = min(slice_time, current.remaining_time)
                    current.remaining_time -= executed
                    if cpu.algorithm == "Round Robin" and cpu.quantum:
                        current.rr_used += executed

                    # Agregar segmento Gantt (apilar si el último segmento es del mismo pid y cpu)
                    if executed > 0:
                        self._append_gantt_segment(cpu.id, current.pid, self.sim_time - executed, executed)

                    # Si el proceso terminó
                    if current.remaining_time <= 1e-9:
                        finish_time = self.sim_time
                        turnaround = finish_time - current.arrival_time
                        waiting = turnaround - current.burst_time

                        print(f"\n=== Proceso {current.pid} completado ===")
                        print(f"sim_time (finish): {finish_time}")
                        print(f"arrival_time: {current.arrival_time}")
                        print(f"burst_time: {current.burst_time}")
                        print(f"turnaround: {turnaround}")
                        print(f"waiting: {waiting}")
                        print(f"=====================================\n")

                        self.completed_info[current.pid] = {
                            'completion': finish_time,
                            'turnaround': turnaround,
                            'waiting': waiting
                        }
                        # Guardar en archivo .txt
                        self.guardar_en_txt(current, self.completed_info[current.pid])

                        # eliminar proceso
                        try:
                            cpu.procesos.pop(0)
                        except Exception:
                            pass
                        # limpiar rr_used si existe
                        if hasattr(current, 'rr_used'):
                            try:
                                delattr(current, 'rr_used')
                            except Exception:
                                try:
                                    del current.rr_used
                                except Exception:
                                    pass
                        # reset assigned set to allow re-adding with same PID if user wants
                        self.assigned_pids.discard(current.pid)
                    else:
                        # En RR, si quantum usado, mover al final
                        if cpu.algorithm == "Round Robin" and cpu.quantum:
                            if current.rr_used >= cpu.quantum - 1e-9:
                                # reset contador rr_used para la siguiente vez
                                try:
                                    current.rr_used = 0.0
                                except Exception:
                                    pass
                                try:
                                    cpu.procesos.append(cpu.procesos.pop(0))
                                except Exception:
                                    pass
                        # En FCFS o SJF no preemption (tal como está diseñado)

                # Usamos un contador simple para actualizar la GUI 1 de cada 3 ticks
                if not hasattr(self, '_frame_skip'): self._frame_skip = 0
                self._frame_skip += 1
                
                if self._frame_skip >= 3: # Ajusta a 5 si sigue lento
                    self.root.after(0, self._gui_update)
                    self._frame_skip = 0

            # ritmo de la simulación
            time.sleep(self.sim_tick)

    def _append_gantt_segment(self, cpu_id, pid, start, duration):
            # Generar color consistente basado en el PID (Hash visual)
            # Esto asegura que el P1 siempre sea del mismo color, P2 de otro, etc.
            import hashlib
            hash_obj = hashlib.md5(str(pid).encode())
            hex_color = '#' + hash_obj.hexdigest()[:6]
            
            # Intentar fusionar con el último segmento DE ESTA MISMA CPU
            merged = False
            # Miramos los últimos 4 segmentos (porque tienes 4 CPUs)
            limit = min(len(self.gantt_segments), 10) 
            
            for i in range(1, limit + 1):
                idx = -i
                seg = self.gantt_segments[idx]
                
                if seg['cpu_id'] == cpu_id:
                    # Es mi CPU. ¿Es mi mismo proceso y es contiguo?
                    # Usamos una tolerancia de 0.05s para errores de flotante
                    ends_at = seg['start'] + seg['duration']
                    if seg['pid'] == pid and abs(ends_at - start) < 0.05:
                        self.gantt_segments[idx]['duration'] += duration
                        merged = True
                    break # Encontré mi CPU, dejo de buscar
            
            if not merged:
                self.gantt_segments.append({
                    'cpu_id': cpu_id,
                    'pid': pid,
                    'start': start,
                    'duration': duration,
                    'color': hex_color # Usamos el color único generado
                })

    def _gui_update(self):
        # Actualizar labels y colas por CPU
        for cpu in self.cpus:
            lbl, lst = self.cpu_frames[cpu.id]
            running = cpu.procesos[0].pid if cpu.procesos else '-'
            lbl.config(text=f"Ejecutando: {running} ({cpu.algorithm})")
            lst.delete(0, tk.END)
            for p in cpu.procesos[1:]:
                lst.insert(tk.END, f"P{p.pid} ({p.remaining_time:.2f}s) Pri:{getattr(p, 'priority', '-')}")
            # también mostrar head (si existe)
            if cpu.procesos:
                lst_head = cpu.procesos[0]
                # mostrar como primer elemento en la lista de la CPU (por claridad)
                lst.insert(0, f"[HEAD] P{lst_head.pid} ({lst_head.remaining_time:.2f}s) Pri:{getattr(lst_head,'priority','-')}")

        # métricas
        completed_count = len(self.completed_info)
        avg_wait = (sum(info['waiting'] for info in self.completed_info.values()) / completed_count) if completed_count else 0.0
        self.avg_wait_label.config(text=f"Espera promedio: {avg_wait:.2f}s")
        self.completed_label.config(text=f"Procesos completados: {completed_count}")

        # actualizar Gantt
        self._draw_gantt()

        # también actualizar la tabla principal
        self.actualizar_tabla()
    def _draw_gantt(self):
        self.gantt_canvas.delete("all")
        
        # --- CONFIGURACIÓN DE ZOOM ---
        window_size = 20.0  # <--- HE BAJADO ESTO A 20s PARA QUE SE VEA MÁS GRANDE
        current_time = self.sim_time
        start_visible_time = max(0.0, current_time - window_size)
        
        # Configuración visual
        x_start, y_base = 60, 40
        row_height = 50     # <--- MÁS ALTO PARA QUE RESPIRE
        bar_height = 30     # <--- ALTURA DE LA BARRA
        
        canvas_width = self.gantt_canvas.winfo_width()
        if canvas_width <= 1: canvas_width = 800 
        scale = (canvas_width - x_start - 20) / window_size

        # 1. Etiquetas CPU
        for i, cpu in enumerate(self.cpus):
            y_pos = y_base + i * row_height
            # Fondo de la fila
            self.gantt_canvas.create_rectangle(0, y_pos, canvas_width, y_pos + row_height, fill="#f8f9fa", outline="")
            # Texto
            self.gantt_canvas.create_text(30, y_pos + row_height/2, text=f"CPU {cpu.id}", font=('Segoe UI', 9, 'bold'))
            # Línea divisoria
            self.gantt_canvas.create_line(x_start, y_pos + row_height, canvas_width, y_pos + row_height, fill="#e2e8f0")

        # 2. Regla de Tiempo
        time_step = 2 # Marcas cada 2 segundos
        first_tick = int(start_visible_time // time_step) * time_step
        for t in range(first_tick, int(current_time) + time_step + 1, time_step):
            if t < start_visible_time: continue
            x_pos = x_start + (t - start_visible_time) * scale
            if x_pos > canvas_width: break
            
            self.gantt_canvas.create_line(x_pos, y_base, x_pos, y_base + (len(self.cpus)*row_height), fill="#cbd5e0", dash=(2,4))
            self.gantt_canvas.create_text(x_pos, y_base - 15, text=f"{t}s", font=('Segoe UI', 8))

        # 3. Segmentos visibles
        for seg in self.gantt_segments:
            seg_end = seg['start'] + seg['duration']
            if seg_end < start_visible_time: continue
            if seg['start'] > current_time: break

            draw_start = max(seg['start'], start_visible_time)
            draw_end = min(seg_end, current_time)
            
            x1 = x_start + (draw_start - start_visible_time) * scale
            x2 = x_start + (draw_end - start_visible_time) * scale
            
            if x2 - x1 < 1: continue

            # Centrar la barra en la fila
            y_center = y_base + (seg['cpu_id'] - 1) * row_height + (row_height/2)
            y1 = y_center - (bar_height/2)
            y2 = y_center + (bar_height/2)

            # --- DIBUJAR CON BORDE NEGRO ---
            self.gantt_canvas.create_rectangle(
                x1, y1, x2, y2, 
                fill=seg['color'], 
                outline='black',  # <--- ESTO DA EL EFECTO DE BLOQUE SÓLIDO
                width=1
            )
            
            # Texto PID (Solo si cabe)
            if x2 - x1 > 25:
                # Color de texto inteligente (blanco o negro según brillo)
                self.gantt_canvas.create_text(
                    (x1 + x2) / 2, y_center, 
                    text=f"P{seg['pid']}", 
                    font=('Segoe UI', 8, 'bold'), 
                    fill="white" # Simplificado a blanco con sombra negra si quieres
                )

        # 4. Línea "Ahora"
        now_x = x_start + (current_time - start_visible_time) * scale
        self.gantt_canvas.create_line(now_x, y_base - 10, now_x, y_base + (len(self.cpus)*row_height), fill="#e53e3e", width=2) 

    # ------------------------- utilidades limpiado -------------------------
    def close(self):
        self.sim_running = False
        self.sim_pause = True
        # cerrar ventana si existe
        try:
            self.sim_win.destroy()
        except Exception:
            pass

    def guardar_en_txt(self, proceso, metrics):
        try:
            with open("procesos_terminados.csv", "a", encoding="utf-8") as f:
                f.write(
                    f"PID: {proceso.pid}, "
                    f"Nombre: {proceso.nombre}, "
                    f"CPU: {getattr(proceso, 'cpu_id', '-')}, "
                    f"CPU Time: {proceso.cpu_time:.2f}, "
                    f"Arrival: {datetime.fromtimestamp(proceso.arrival_time)}, "
                    f"Completion: {metrics['completion']:.2f}, "
                    f"Turnaround: {metrics['turnaround']:.2f}, "
                    f"Waiting: {metrics['waiting']:.2f}\n"
                )
        except Exception as e:
            print("Error al guardar:", e)
