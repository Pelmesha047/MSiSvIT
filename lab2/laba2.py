#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Графическое приложение (GUI) и CLI-анализатор метрик сложности потока управления
для кода на языке Perl (согласно методическим указаниям).

Вычисляемые метрики:
1. Метрика Маккейба (Цикломатическая сложность графа программы):
   - Z(G) = e - v + 2p
   где e — число дуг, v — число вершин, p — число компонентов связности.

2. Метрики Джилба (Логическая сложность):
   - CL: Абсолютная сложность (количество условных операторов и разветвлений)
   - cl: Относительная сложность (насыщенность условными операторами = CL / всего операторов)
   - CLI: Максимальный уровень вложенности условных операторов и циклов

3. Метрика граничных значений (Boundary Value Metric):
   - Sa: Абсолютная граничная сложность (сумма скорректированных сложностей всех вершин графа)
   - S0: Относительная граничная сложность S0 = 1 - (v - 1) / Sa
"""

import sys
import os
import re
import math
from collections import Counter, defaultdict, deque
from typing import Dict, List, Tuple, Any, Set, Optional

# Подключение библиотеки GUI (Tkinter)
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

# Настройка UTF-8 для консоли Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ============================================================================
# СТРУКТУРЫ ДАННЫХ УПРАВЛЯЮЩЕГО ГРАФА (CFG)
# ============================================================================

class CFGNode:
    """Вершина управляющего графа (CFG)."""
    def __init__(self, node_id: int, label: str, node_type: str = 'statement', line_no: int = 0, nesting_level: int = 0):
        self.id = node_id
        self.label = label
        self.type = node_type  # 'start', 'statement', 'decision', 'exit'
        self.line_no = line_no
        self.nesting_level = nesting_level
        self.out_edges: List[Tuple[int, str]] = []  # (target_node_id, branch_label)
        self.in_edges: List[Tuple[int, str]] = []   # (source_node_id, branch_label)
        self.adjusted_complexity: int = 1

    @property
    def out_degree(self) -> int:
        return len(self.out_edges)

    @property
    def in_degree(self) -> int:
        return len(self.in_edges)

    def __repr__(self):
        return f"<Node {self.id}: {self.type} '{self.label}'>"


class ControlFlowGraph:
    """Ориентированный граф управления (CFG)."""
    def __init__(self):
        self.nodes: Dict[int, CFGNode] = {}
        self.start_node_id: Optional[int] = None
        self.exit_node_id: Optional[int] = None
        self._next_id = 1

    def create_node(self, label: str, node_type: str = 'statement', line_no: int = 0, nesting_level: int = 0) -> CFGNode:
        node_id = self._next_id
        self._next_id += 1
        node = CFGNode(node_id, label, node_type, line_no, nesting_level)
        self.nodes[node_id] = node
        return node

    def add_edge(self, from_id: int, to_id: int, branch_label: str = ''):
        if from_id in self.nodes and to_id in self.nodes:
            # Избегаем дубликатов точных ребер
            if not any(target == to_id and lbl == branch_label for target, lbl in self.nodes[from_id].out_edges):
                self.nodes[from_id].out_edges.append((to_id, branch_label))
                self.nodes[to_id].in_edges.append((from_id, branch_label))

    def get_all_edges(self) -> List[Tuple[int, int, str]]:
        edges = []
        for src_id, node in self.nodes.items():
            for target_id, lbl in node.out_edges:
                edges.append((src_id, target_id, lbl))
        return edges


# ============================================================================
# АНАЛИЗАТОР ПОТОКА УПРАВЛЕНИЯ PERL (PARSER & CFG BUILDER)
# ============================================================================

class PerlControlFlowAnalyzer:
    """Класс для токенизации, построения CFG и вычисления метрик управления."""

    CONTROL_KEYWORDS = {'if', 'elsif', 'unless', 'while', 'until', 'for', 'foreach', 'given', 'when', 'default'}

    def __init__(self):
        pass

    def tokenize(self, code: str) -> List[Dict[str, Any]]:
        """Токенизация Perl-кода на лексемы с отслеживанием номеров строк."""
        token_specification = [
            ('COMMENT',   r'#.*'),
            ('STRING',    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`|q[qwxr]?\s*\/[^\/]*\/|q[qwxr]?\s*\{[^{}]*\}'),
            ('REGEX',     r'(?:s|tr|y)\/[^\/]*\/[^\/]*\/[a-z]*|m\/[^\/]*\/[a-z]*'),
            ('VARIABLE',  r'[\$@%]\#?\{?[a-zA-Z_][a-zA-Z0-9_]*\}?|\$\d+|\$_|@_'),
            ('NUMBER',    r'\b\d+(?:\.\d+)?\b'),
            ('SYM_OP',    r'\.\.\.|->|=>|\+\+|--|==|!=|<=|>=|&&|\|\||//|\+=|-=|\*=|\/=|&&=|\|\|=|\?|:|[;{},]'),
            ('WORD',      r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),
            ('BRACKET',   r'[\(\)\[\]]'),
            ('NEWLINE',   r'\n'),
            ('SKIP',      r'[ \t\r]+'),
            ('MISC',      r'.'),
        ]

        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_specification)
        line_num = 1
        line_start = 0

        tokens = []
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'NEWLINE':
                line_num += 1
                line_start = mo.end()
                continue
            elif kind in ('SKIP', 'COMMENT'):
                continue
            
            tokens.append({
                'kind': kind,
                'value': value,
                'line': line_num
            })

        return tokens

    def parse_and_build_cfg(self, code: str) -> Tuple[ControlFlowGraph, Dict[str, Any]]:
        """Разбор кода Perl и построение управляющего графа CFG."""
        tokens = self.tokenize(code)
        cfg = ControlFlowGraph()

        # Создаем начальную вершину
        start_node = cfg.create_node("Старт программы", node_type='start', line_no=1, nesting_level=0)
        cfg.start_node_id = start_node.id

        # Базовый счетчик операторов и уровней вложенности
        cl_count = 0
        total_statements = 0
        max_cli = 0
        current_nesting = 0

        gilb_details = []  # Данные для таблицы Джилба

        # Разбиваем токены на простейшие условные и циклические конструкторы
        lines = code.splitlines()
        statement_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
        total_statements = len(statement_lines) if statement_lines else 1

        # Отслеживание блоков и условных операторов в коде
        # Подсчет операторов Джилба и глубины вложенности
        in_code_nesting = 0
        
        i = 0
        n_tokens = len(tokens)

        # Дерево операторов управления для генерации CFG
        # Простой и надежный генератор узлов CFG по управляющим структурам
        nodes_chain: List[CFGNode] = [start_node]

        prev_node = start_node
        
        # Стек открытых блоков циклов/условий: list of dicts
        # dict: {'type': 'if'/'while'/'for'/'do', 'decision_node': CFGNode, 'merge_node': CFGNode, 'nesting': int}
        block_stack = []

        while i < n_tokens:
            tok = tokens[i]
            val = tok['value']
            kind = tok['kind']
            line = tok['line']

            if val == '{':
                in_code_nesting += 1
                if in_code_nesting > max_cli:
                    max_cli = in_code_nesting
                i += 1
                continue
            elif val == '}':
                if in_code_nesting > 0:
                    in_code_nesting -= 1
                if block_stack and block_stack[-1].get('brace_depth') == in_code_nesting + 1:
                    b_info = block_stack.pop()
                    b_type = b_info['type']
                    m_node = b_info['merge_node']
                    d_node = b_info['decision_node']

                    if b_type in ('if', 'elsif', 'unless'):
                        # Текущая ветка соединяется с точкой слияния
                        cfg.add_edge(prev_node.id, m_node.id, "Завершение ветки")
                        prev_node = m_node
                    elif b_type in ('while', 'until', 'for', 'foreach'):
                        # Зацикливание из конца тела назад к условию
                        cfg.add_edge(prev_node.id, d_node.id, "Петля (повтор)")
                        prev_node = m_node
                    elif b_type == 'do':
                        pass
                i += 1
                continue

            # Условный оператор IF / ELSIF / UNLESS
            if kind == 'WORD' and val in ('if', 'elsif', 'unless'):
                # Проверка: постфиксная форма (statement if condition;)
                is_postfix = False
                if i > 0 and tokens[i-1]['value'] not in (';', '{', '}', 'do'):
                    is_postfix = True

                cl_count += 1
                
                # Расчет уровня вложенности в соответствии с требованиями преподавателя:
                # В цепочках if-elsif-elsif каждая следующая ветка считается вложенной в предыдущую
                effective_nesting = in_code_nesting
                if val == 'elsif' and block_stack:
                    # Ищем активную цепочку if/elsif
                    for b_info in reversed(block_stack):
                        if b_info['type'] in ('if', 'elsif'):
                            b_info['chain_depth'] = b_info.get('chain_depth', 0) + 1
                            effective_nesting += b_info['chain_depth']
                            break

                if effective_nesting > max_cli:
                    max_cli = effective_nesting

                gilb_details.append({
                    'line': line,
                    'operator': val,
                    'type': 'Условный оператор (постфиксный)' if is_postfix else 'Условный оператор',
                    'nesting': effective_nesting
                })

                # Извлечение условия
                cond_text = self._extract_condition(tokens, i + 1)
                
                # Создаем узел решения (Decision Node)
                d_node = cfg.create_node(
                    f"{val} ({cond_text})",
                    node_type='decision',
                    line_no=line,
                    nesting_level=effective_nesting
                )
                
                # Соединяем предыдущий узел с узлом решения
                cfg.add_edge(prev_node.id, d_node.id, "Переход")

                # Узел слияния (Merge Point после блока)
                m_node = cfg.create_node(
                    f"Слияние {val} [строка {line}]",
                    node_type='statement',
                    line_no=line,
                    nesting_level=effective_nesting
                )

                # Ветвь True (выполнение тела)
                body_start_node = cfg.create_node(
                    f"Тело {val} [строка {line}]",
                    node_type='statement',
                    line_no=line,
                    nesting_level=effective_nesting + 1
                )
                cfg.add_edge(d_node.id, body_start_node.id, "Да (True)")

                # Ветвь False (обход / следующая ветка)
                cfg.add_edge(d_node.id, m_node.id, "Нет (False)")

                block_stack.append({
                    'type': val,
                    'decision_node': d_node,
                    'merge_node': m_node,
                    'brace_depth': in_code_nesting + 1,
                    'chain_depth': 0
                })

                prev_node = body_start_node

            # Конструкция ELSE
            elif kind == 'WORD' and val == 'else':
                if block_stack and block_stack[-1]['type'] in ('if', 'elsif', 'unless'):
                    last_b = block_stack[-1]
                    m_node = last_b['merge_node']
                    # Соединяем предыдущий узел ветки True с точкой слияния
                    cfg.add_edge(prev_node.id, m_node.id, "Конец ветви if/elsif")
                    
                    effective_nesting = in_code_nesting + last_b.get('chain_depth', 0) + 1
                    if effective_nesting > max_cli:
                        max_cli = effective_nesting

                    else_body_node = cfg.create_node(
                        f"Тело else [строка {line}]",
                        node_type='statement',
                        line_no=line,
                        nesting_level=effective_nesting
                    )
                    # False путь последнего условного узла перенаправляем в else body
                    prev_node = else_body_node

            # Циклы WHILE / UNTIL / FOR / FOREACH
            elif kind == 'WORD' and val in ('while', 'until', 'for', 'foreach'):
                cl_count += 1
                effective_nesting = in_code_nesting
                if effective_nesting > max_cli:
                    max_cli = effective_nesting

                gilb_details.append({
                    'line': line,
                    'operator': val,
                    'type': 'Оператор цикла',
                    'nesting': effective_nesting
                })

                cond_text = self._extract_condition(tokens, i + 1)
                
                d_node = cfg.create_node(
                    f"Цикл {val} ({cond_text})",
                    node_type='decision',
                    line_no=line,
                    nesting_level=effective_nesting
                )

                cfg.add_edge(prev_node.id, d_node.id, "Вход в цикл")

                m_node = cfg.create_node(
                    f"Выход из цикла {val} [строка {line}]",
                    node_type='statement',
                    line_no=line,
                    nesting_level=effective_nesting
                )

                body_node = cfg.create_node(
                    f"Тело цикла {val} [строка {line}]",
                    node_type='statement',
                    line_no=line,
                    nesting_level=effective_nesting + 1
                )

                # Ветвь условия цикла
                cfg.add_edge(d_node.id, body_node.id, "Условие выполнено (Да)")
                cfg.add_edge(d_node.id, m_node.id, "Выход из цикла (Нет)")

                block_stack.append({
                    'type': val,
                    'decision_node': d_node,
                    'merge_node': m_node,
                    'brace_depth': in_code_nesting + 1,
                    'chain_depth': 0
                })

                prev_node = body_node

            # Однострочные или последовательные операторы
            elif val == ';' and prev_node.type == 'statement':
                pass

            # Тернарный оператор ? :
            elif val == '?':
                cl_count += 1
                effective_nesting = in_code_nesting
                if effective_nesting > max_cli:
                    max_cli = effective_nesting

                gilb_details.append({
                    'line': line,
                    'operator': '?:',
                    'type': 'Тернарный оператор',
                    'nesting': effective_nesting
                })
                
                d_node = cfg.create_node(
                    f"Тернарный выбор ? [строка {line}]",
                    node_type='decision',
                    line_no=line,
                    nesting_level=effective_nesting
                )
                cfg.add_edge(prev_node.id, d_node.id, "Вычисление")
                
                m_node = cfg.create_node(
                    f"Результат ?: [строка {line}]",
                    node_type='statement',
                    line_no=line,
                    nesting_level=effective_nesting
                )
                cfg.add_edge(d_node.id, m_node.id, "Ветвь 1")
                cfg.add_edge(d_node.id, m_node.id, "Ветвь 2")
                prev_node = m_node

            # Разветвления GIVEN / WHEN / DEFAULT
            elif kind == 'WORD' and val == 'when':
                cl_count += 1
                effective_nesting = in_code_nesting
                if block_stack:
                    for b_info in reversed(block_stack):
                        if b_info['type'] in ('given', 'when'):
                            b_info['chain_depth'] = b_info.get('chain_depth', 0) + 1
                            effective_nesting += b_info['chain_depth']
                            break

                if effective_nesting > max_cli:
                    max_cli = effective_nesting

                gilb_details.append({
                    'line': line,
                    'operator': 'when',
                    'type': 'Ветвь переключателя (given/when)',
                    'nesting': effective_nesting
                })
                d_node = cfg.create_node(
                    f"when [строка {line}]",
                    node_type='decision',
                    line_no=line,
                    nesting_level=effective_nesting
                )
                cfg.add_edge(prev_node.id, d_node.id, "Проверка совпадения")
                prev_node = d_node

            i += 1

        # Финальный узел выхода из программы
        exit_node = cfg.create_node("Конец программы", node_type='exit', line_no=n_tokens, nesting_level=0)
        cfg.exit_node_id = exit_node.id
        cfg.add_edge(prev_node.id, exit_node.id, "Завершение")

        # Если в графе есть висячие узлы без исходящих ребер (кроме exit_node), связываем их с exit_node
        for nid, node in list(cfg.nodes.items()):
            if nid != exit_node.id and node.out_degree == 0:
                cfg.add_edge(nid, exit_node.id, "Переход к концу")

        # Формирование результатов Джилба
        cl_relative = (cl_count / total_statements) if total_statements > 0 else 0.0

        gilb_metrics = {
            'CL': cl_count,
            'cl': cl_relative,
            'CLI': max_cli,
            'total_statements': total_statements,
            'details': gilb_details
        }

        return cfg, gilb_metrics

    def _extract_condition(self, tokens: List[Dict[str, Any]], start_idx: int) -> str:
        """Вспомогательная функция для извлечения строкового представления условия из круглых скобок."""
        cond_tokens = []
        paren_depth = 0
        idx = start_idx
        n = len(tokens)

        # Пропускаем возможные пробелы до '('
        while idx < n and tokens[idx]['value'] != '(':
            idx += 1

        if idx < n and tokens[idx]['value'] == '(':
            paren_depth = 1
            cond_tokens.append('(')
            idx += 1
            while idx < n and paren_depth > 0:
                val = tokens[idx]['value']
                if val == '(':
                    paren_depth += 1
                elif val == ')':
                    paren_depth -= 1
                cond_tokens.append(val)
                idx += 1

        cond_str = " ".join(cond_tokens)
        if len(cond_str) > 40:
            cond_str = cond_str[:37] + "..."
        return cond_str or "cond"

    def calculate_boundary_metrics(self, cfg: ControlFlowGraph) -> Tuple[int, float, Dict[int, int]]:
        """
        Расчет метрики граничных значений (Boundary Value Metric):
        - Sa: Абсолютная граничная сложность (сумма скорректированных сложностей всех вершин)
        - S0: Относительная граничная сложность S0 = 1 - (v - 1) / Sa
        - adjusted_complexities: словарь {node_id: complexity}
        """
        adj_comp = {}
        v_total = len(cfg.nodes)

        # 1. Принимающие вершины (out_degree <= 1): скорректированная сложность = 1
        # 2. Конечная вершина (out_degree == 0): скорректированная сложность = 0
        # 3. Вершины выбора / решения (out_degree >= 2): скорректированная сложность =
        #    число вершин подграфа (исключая саму вершину выбора), доступных до нижней границы подграфа.

        for nid, node in cfg.nodes.items():
            if node.type == 'exit' or node.out_degree == 0:
                adj_comp[nid] = 0
            elif node.out_degree <= 1:
                adj_comp[nid] = 1
            else:
                # Вершина выбора (Decision node: out_degree >= 2)
                # Вычисляем подграф, достижимый из дочерних веток до ближайшей совместной границы
                subgraph_nodes = self._find_decision_subgraph(cfg, nid)
                # Исключаем саму вершину выбора из подграфа
                subgraph_size = max(1, len(subgraph_nodes - {nid}))
                adj_comp[nid] = subgraph_size

            node.adjusted_complexity = adj_comp[nid]

        Sa = sum(adj_comp.values())
        
        if Sa > 0 and v_total > 1:
            S0 = 1.0 - ((v_total - 1) / Sa)
        else:
            S0 = 0.0

        return Sa, S0, adj_comp

    def _find_decision_subgraph(self, cfg: ControlFlowGraph, decision_id: int) -> Set[int]:
        """Поиск подграфа, управляемого вершиной выбора decision_id."""
        visited = set()
        queue = deque()

        # Добавляем все прямо получающие вершины из ветвей решения
        for target_id, _ in cfg.nodes[decision_id].out_edges:
            queue.append(target_id)
            visited.add(target_id)

        # Обход в ширину подграфа веток до точки схождения (где out_degree снижается)
        depth_limit = 15
        current_depth = 0

        while queue and current_depth < depth_limit:
            size = len(queue)
            for _ in range(size):
                curr = queue.popleft()
                node = cfg.nodes.get(curr)
                if not node or node.type == 'exit':
                    continue

                for next_id, _ in node.out_edges:
                    if next_id not in visited and next_id != decision_id:
                        visited.add(next_id)
                        queue.append(next_id)
            current_depth += 1

        return visited

    def analyze(self, code: str) -> Dict[str, Any]:
        """Полный анализ Perl-кода по всем метрикам потока управления."""
        cfg, gilb_metrics = self.parse_and_build_cfg(code)
        
        v = len(cfg.nodes)
        e = len(cfg.get_all_edges())
        p = 1  # Для связной программы количество компонентов связности = 1

        # Метрика Маккейба: Z(G) = e - v + 2p
        mccabe_z = e - v + 2 * p
        if mccabe_z < 1:
            mccabe_z = 1

        # Метрики граничных значений: Sa и S0
        Sa, S0, adj_comp = self.calculate_boundary_metrics(cfg)

        return {
            'cfg': cfg,
            'v': v,
            'e': e,
            'p': p,
            'mccabe_z': mccabe_z,
            'gilb': gilb_metrics,
            'Sa': Sa,
            'S0': S0,
            'adj_comp': adj_comp
        }


# ============================================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (GUI на Tkinter)
# ============================================================================

class ControlFlowGUIApp:
    """Класс графического интерфейса пользователя (GUI) на Tkinter."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Анализатор метрик сложности потока управления (Perl)")
        self.root.geometry("1180x850")
        self.root.minsize(980, 700)

        self.analyzer = PerlControlFlowAnalyzer()
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground="#1a365d")
        style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground="#1a365d")
        style.configure("MetricMain.TLabel", font=("Consolas", 11, "bold"), foreground="#2b6cb0")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", font=("Consolas", 10), rowheight=24)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Верхняя панель: Заголовок и кнопки управления
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 8))

        title_label = ttk.Label(
            header_frame,
            text="Метрики сложности потока управления (Маккейб, Джилб, Граничные значения)",
            style="Title.TLabel"
        )
        title_label.pack(side=tk.LEFT, padx=(0, 10))

        btn_bar = ttk.Frame(header_frame)
        btn_bar.pack(side=tk.RIGHT)

        ttk.Button(btn_bar, text="📁 Открыть файл...", command=self._load_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✨ Пример 1 (Sin1)", command=self._insert_example_1).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✨ Пример 2 (If-Elsif)", command=self._insert_example_2).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="🗑 Очистить", command=self._clear_input).pack(side=tk.LEFT, padx=3)

        # 2. Разделитель верхнего текстового поля и нижних таблиц
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 2.1 Верхняя секция: Текстовое поле для ввода кода
        input_frame = ttk.LabelFrame(paned, text=" Исходный код Perl для анализа ", padding=5)
        paned.add(input_frame, weight=1)

        self.text_code = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        self.text_code.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        btn_run = tk.Button(
            input_frame,
            text="▶ РАССЧИТАТЬ МЕТРИКИ ПОТОКА УПРАВЛЕНИЯ",
            bg="#2b6cb0",
            fg="white",
            font=("Segoe UI", 11, "bold"),
            activebackground="#2c5282",
            activeforeground="white",
            cursor="hand2",
            relief=tk.RAISED,
            bd=2,
            command=self._analyze_code
        )
        btn_run.pack(fill=tk.X, pady=(5, 0))

        # 2.2 Нижняя секция: Вкладки с таблицами и итоговые метрики
        results_frame = ttk.LabelFrame(paned, text=" Результаты анализа графа управления ", padding=5)
        paned.add(results_frame, weight=2)

        notebook = ttk.Notebook(results_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Вкладка 1: Вершины управляющего графа (CFG Nodes)
        tab_nodes = ttk.Frame(notebook)
        notebook.add(tab_nodes, text=" Таблица 1. Вершины графа (V) ")

        self.tree_nodes = ttk.Treeview(
            tab_nodes,
            columns=("id", "type", "label", "out_deg", "adj_comp"),
            show="headings",
            height=8
        )
        self.tree_nodes.heading("id", text="№ (v)")
        self.tree_nodes.heading("type", text="Тип вершины")
        self.tree_nodes.heading("label", text="Метка / Оператор")
        self.tree_nodes.heading("out_deg", text="Исх. степень (+deg)")
        self.tree_nodes.heading("adj_comp", text="Скорректир. сложность S(v)")

        self.tree_nodes.column("id", width=60, anchor=tk.CENTER)
        self.tree_nodes.column("type", width=140, anchor=tk.W)
        self.tree_nodes.column("label", width=420, anchor=tk.W)
        self.tree_nodes.column("out_deg", width=140, anchor=tk.CENTER)
        self.tree_nodes.column("adj_comp", width=190, anchor=tk.CENTER)

        nodes_scroll = ttk.Scrollbar(tab_nodes, orient=tk.VERTICAL, command=self.tree_nodes.yview)
        self.tree_nodes.configure(yscrollcommand=nodes_scroll.set)

        self.tree_nodes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nodes_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Вкладка 2: Дуги управляющего графа (CFG Edges)
        tab_edges = ttk.Frame(notebook)
        notebook.add(tab_edges, text=" Таблица 2. Дуги графа (E) ")

        self.tree_edges = ttk.Treeview(
            tab_edges,
            columns=("idx", "from", "to", "lbl"),
            show="headings",
            height=8
        )
        self.tree_edges.heading("idx", text="№ дуги (e)")
        self.tree_edges.heading("from", text="Исходная вершина (v)")
        self.tree_edges.heading("to", text="Конечная вершина (u)")
        self.tree_edges.heading("lbl", text="Условие / Направление перехода")

        self.tree_edges.column("idx", width=80, anchor=tk.CENTER)
        self.tree_edges.column("from", width=220, anchor=tk.W)
        self.tree_edges.column("to", width=220, anchor=tk.W)
        self.tree_edges.column("lbl", width=400, anchor=tk.W)

        edges_scroll = ttk.Scrollbar(tab_edges, orient=tk.VERTICAL, command=self.tree_edges.yview)
        self.tree_edges.configure(yscrollcommand=edges_scroll.set)

        self.tree_edges.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        edges_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Вкладка 3: Операторы Джилба
        tab_gilb = ttk.Frame(notebook)
        notebook.add(tab_gilb, text=" Таблица 3. Детализация Метрики Джилба ")

        self.tree_gilb = ttk.Treeview(
            tab_gilb,
            columns=("idx", "line", "op", "type", "nesting"),
            show="headings",
            height=8
        )
        self.tree_gilb.heading("idx", text="№")
        self.tree_gilb.heading("line", text="Строка")
        self.tree_gilb.heading("op", text="Оператор выбора")
        self.tree_gilb.heading("type", text="Категория конструкта")
        self.tree_gilb.heading("nesting", text="Глубина вложенности")

        self.tree_gilb.column("idx", width=50, anchor=tk.CENTER)
        self.tree_gilb.column("line", width=90, anchor=tk.CENTER)
        self.tree_gilb.column("op", width=180, anchor=tk.W)
        self.tree_gilb.column("type", width=360, anchor=tk.W)
        self.tree_gilb.column("nesting", width=180, anchor=tk.CENTER)

        gilb_scroll = ttk.Scrollbar(tab_gilb, orient=tk.VERTICAL, command=self.tree_gilb.yview)
        self.tree_gilb.configure(yscrollcommand=gilb_scroll.set)

        self.tree_gilb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        gilb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Настройка копирования для всех таблиц
        self._setup_treeview_copy(self.tree_nodes)
        self._setup_treeview_copy(self.tree_edges)
        self._setup_treeview_copy(self.tree_gilb)

        # 3. Итоговая панель с рассчитанными метриками
        summary_frame = ttk.LabelFrame(results_frame, text=" Сводный расчет метрик сложности ", padding=8)
        summary_frame.pack(fill=tk.X, pady=4)

        self.lbl_mccabe = ttk.Label(
            summary_frame,
            text="1. МЕТРИКА МАККЕЙБА: Z(G) = e - v + 2p = 0  (дуг e = 0, вершин v = 0, p = 1)",
            style="MetricMain.TLabel"
        )
        self.lbl_mccabe.pack(fill=tk.X, pady=2)

        self.lbl_gilb = ttk.Label(
            summary_frame,
            text="2. МЕТРИКИ ДЖИЛБА:  Абсолютная CL = 0  |  Относительная cl = 0.000  |  Макс. вложенность CLI = 0",
            font=("Consolas", 11, "bold"),
            foreground="#2c5282"
        )
        self.lbl_gilb.pack(fill=tk.X, pady=2)

        self.lbl_boundary = ttk.Label(
            summary_frame,
            text="3. ГРАНИЧНЫЕ МЕТРИКИ: Абсолютная сложность Sa = 0  |  Относительная сложность S0 = 0.000",
            font=("Consolas", 11, "bold"),
            foreground="#276749"
        )
        self.lbl_boundary.pack(fill=tk.X, pady=2)

        # Заполнение примером 1 при старте
        self._insert_example_1()

    def _insert_example_1(self):
        example_code = '''# Пример 1: Итерационный расчет sin(x) через ряд Тейлора (do...until)
my $eps = 0.0001;
my $x = 0.5;
my $y = $x;
my $n = 2;
my $vs = $x;

do {
    $vs = -$vs * $x * $x / (2 * $n - 1) / (2 * $n - 2);
    $n = $n + 1;
    $y = $y + $vs;
} until (abs($vs) < $eps);

print($x, $y, $eps);
'''
        self.text_code.delete("1.0", tk.END)
        self.text_code.insert(tk.END, example_code)
        self._analyze_code()

    def _insert_example_2(self):
        example_code = '''# Пример 2: Разветвленный алгоритм (If - Elsif - Else)
my $score = 85;
my $grade = 'F';

if ($score >= 90) {
    $grade = 'A';
} elsif ($score >= 80) {
    if ($score >= 85) {
        $grade = 'B+';
    } else {
        $grade = 'B';
    }
} elsif ($score >= 70) {
    $grade = 'C';
} else {
    $grade = 'D';
}

print("Grade: ", $grade);
'''
        self.text_code.delete("1.0", tk.END)
        self.text_code.insert(tk.END, example_code)
        self._analyze_code()

    def _clear_input(self):
        self.text_code.delete("1.0", tk.END)

    def _load_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Perl Files", "*.pl *.pm"), ("All Files", "*.*")])
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.text_code.delete("1.0", tk.END)
                self.text_code.insert(tk.END, content)
                self._analyze_code()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")

    def _analyze_code(self):
        code = self.text_code.get("1.0", tk.END)
        if not code.strip():
            messagebox.showwarning("Предупреждение", "Введите код Perl для анализа!")
            return

        res = self.analyzer.analyze(code)
        cfg: ControlFlowGraph = res['cfg']

        # Очистка таблиц
        for item in self.tree_nodes.get_children():
            self.tree_nodes.delete(item)
        for item in self.tree_edges.get_children():
            self.tree_edges.delete(item)
        for item in self.tree_gilb.get_children():
            self.tree_gilb.delete(item)

        # 1. Заполнение Таблицы 1 (Вершины V)
        type_names = {
            'start': 'Начало (Start)',
            'statement': 'Принимающая (Statement)',
            'decision': 'Вершина выбора (Decision)',
            'exit': 'Конец (Exit)'
        }

        for nid, node in sorted(cfg.nodes.items()):
            t_str = type_names.get(node.type, node.type)
            adj = res['adj_comp'].get(nid, 1)
            self.tree_nodes.insert("", tk.END, values=(
                node.id,
                t_str,
                node.label,
                node.out_degree,
                adj
            ))

        # 2. Заполнение Таблицы 2 (Дуги E)
        edges = cfg.get_all_edges()
        for idx, (src_id, tgt_id, lbl) in enumerate(sorted(edges), 1):
            src_node = cfg.nodes.get(src_id)
            tgt_node = cfg.nodes.get(tgt_id)
            src_str = f"v{src_id}: {src_node.label if src_node else ''}"
            tgt_str = f"u{tgt_id}: {tgt_node.label if tgt_node else ''}"
            self.tree_edges.insert("", tk.END, values=(idx, src_str, tgt_str, lbl or "Переход"))

        # 3. Заполнение Таблицы 3 (Джилб)
        gilb_info = res['gilb']
        for idx, item in enumerate(gilb_info['details'], 1):
            self.tree_gilb.insert("", tk.END, values=(
                idx,
                item['line'],
                item['operator'],
                item['type'],
                item['nesting']
            ))

        # 4. Обновление сводных метрик
        self.lbl_mccabe.config(
            text=f"1. МЕТРИКА МАККЕЙБА: Z(G) = {res['e']} - {res['v']} + 2({res['p']}) = {res['mccabe_z']}  (Число независимых путей = {res['mccabe_z']})"
        )
        self.lbl_gilb.config(
            text=f"2. МЕТРИКИ ДЖИЛБА:  Абсолютная CL = {gilb_info['CL']}  |  Относительная cl = {gilb_info['cl']:.3f} ({gilb_info['cl']*100:.1f}%)  |  Макс. вложенность CLI = {gilb_info['CLI']}"
        )
        self.lbl_boundary.config(
            text=f"3. ГРАНИЧНЫЕ МЕТРИКИ: Абсолютная сложность Sa = {res['Sa']}  |  Относительная сложность S0 = {res['S0']:.3f}"
        )

    def _setup_treeview_copy(self, tree: ttk.Treeview):
        """Настраивает горячие клавиши (Ctrl+C, Ctrl+A) и контекстное меню по правому клику для таблицы."""
        tree.bind("<Control-c>", lambda e: self._copy_treeview_to_clipboard(tree))
        tree.bind("<Control-C>", lambda e: self._copy_treeview_to_clipboard(tree))
        tree.bind("<Control-Insert>", lambda e: self._copy_treeview_to_clipboard(tree))

        def select_all(event):
            tree.selection_set(tree.get_children())
            return "break"

        tree.bind("<Control-a>", select_all)
        tree.bind("<Control-A>", select_all)

        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(
            label="📋 Скопировать выделенное (Ctrl+C)",
            command=lambda: self._copy_treeview_to_clipboard(tree, only_selected=True)
        )
        menu.add_command(
            label="📊 Скопировать всю таблицу",
            command=lambda: self._copy_treeview_to_clipboard(tree, only_selected=False)
        )

        def show_context_menu(event):
            item = tree.identify_row(event.y)
            if item and item not in tree.selection():
                tree.selection_set(item)
            menu.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", show_context_menu)
        tree.bind("<Button-2>", show_context_menu)

    def _copy_treeview_to_clipboard(self, tree: ttk.Treeview, only_selected: bool = None, event=None):
        if only_selected is True:
            items = tree.selection()
        elif only_selected is False:
            items = tree.get_children()
        else:
            items = tree.selection()
            if not items:
                items = tree.get_children()

        if not items:
            return "break"

        columns = tree["columns"]
        headers = [tree.heading(col)["text"] for col in columns]

        rows = ["\t".join(headers)]
        for item_id in items:
            values = tree.item(item_id, "values")
            rows.append("\t".join(str(v) for v in values))

        text_data = "\n".join(rows)

        self.root.clipboard_clear()
        self.root.clipboard_append(text_data)
        self.root.update()

        return "break"


# ============================================================================
# ВЫВОД В КОНСОЛЬ (CLI РЕЖИМ)
# ============================================================================

def print_cli_results(results: Dict[str, Any]):
    """Выводит результаты анализа метрик сложности потока управления в консоль."""
    cfg: ControlFlowGraph = results['cfg']
    gilb = results['gilb']

    print("\n" + "=" * 78)
    print("      РАСЧЁТ МЕТРИК СЛОЖНОСТИ ПОТОКА УПРАВЛЕНИЯ ПРОГРАММЫ (PERL)")
    print("=" * 78)

    print("\nТаблица 1. Вершины управляющего графа CFG (V)")
    print("-" * 78)
    print(f"{'ID (v)':<8} {'Тип вершины':<24} {'Степень (+deg)':<15} {'Скорректир. S(v)':<18}")
    print("-" * 78)
    for nid, node in sorted(cfg.nodes.items()):
        print(f"{node.id:<8} {node.type:<24} {node.out_degree:<15} {node.adjusted_complexity:<18}")
    print("-" * 78)

    print("\nТаблица 2. Дуги управляющего графа CFG (E)")
    print("-" * 78)
    print(f"{'№':<5} {'Откуда (v)':<15} {'Куда (u)':<15} {'Условие/Направление':<35}")
    print("-" * 78)
    for idx, (src_id, tgt_id, lbl) in enumerate(sorted(cfg.get_all_edges()), 1):
        print(f"{idx:<5} v{src_id:<14} u{tgt_id:<14} {lbl or 'Переход':<35}")
    print("-" * 78)

    print("\n" + "─" * 55)
    print("  1. МЕТРИКА МАККЕЙБА (Цикломатическая сложность)")
    print("─" * 55)
    print(f"  • Число вершин (v)                  = {results['v']}")
    print(f"  • Число дуг (e)                     = {results['e']}")
    print(f"  • Компоненты связности (p)          = {results['p']}")
    print(f"  • Цикломатическое число Z(G) = e-v+2p = {results['mccabe_z']}")
    print(f"    (Минимальное число базисных тестовых прогонов: {results['mccabe_z']})")

    print("\n" + "─" * 55)
    print("  2. МЕТРИКИ ДЖИЛБА (Логическая сложность)")
    print("─" * 55)
    print(f"  • Абсолютная сложность CL           = {gilb['CL']}")
    print(f"  • Относительная сложность cl        = {gilb['cl']:.4f} ({gilb['cl']*100:.2f}%)")
    print(f"  • Максимальная вложенность CLI      = {gilb['CLI']}")
    print(f"  • Всего операторов программы        = {gilb['total_statements']}")

    print("\n" + "─" * 55)
    print("  3. МЕТРИКА ГРАНИЧНЫХ ЗНАЧЕНИЙ")
    print("─" * 55)
    print(f"  • Абсолютная граничная сложность Sa = {results['Sa']}")
    print(f"  • Относительная граничная сложность S0= {results['S0']:.4f}")
    print("=" * 78 + "\n")


def main():
    """Точка входа: запускает GUI при отсутствии аргументов либо CLI при их наличии."""
    if len(sys.argv) > 1 or not sys.stdin.isatty():
        code = ""
        if len(sys.argv) > 1:
            filepath = sys.argv[1]
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                print(f"[+] Прочитан файл: {filepath}")
            except Exception as e:
                print(f"[-] Ошибка чтения файла {filepath}: {e}")
                sys.exit(1)
        else:
            code = sys.stdin.read()

        if code.strip():
            analyzer = PerlControlFlowAnalyzer()
            results = analyzer.analyze(code)
            print_cli_results(results)
        else:
            print("ОШИБКА: Код не передан!")
    else:
        if HAS_TKINTER:
            root = tk.Tk()
            app = ControlFlowGUIApp(root)
            root.mainloop()
        else:
            print("ОШИБКА: Модуль tkinter недоступен в данной системе!")


if __name__ == "__main__":
    main()
