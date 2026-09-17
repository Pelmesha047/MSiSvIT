#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Графическое приложение (GUI) и CLI-анализатор метрик Холстеда для кода на языке Perl.
Анализирует исходный код Perl и вычисляет:
  - 6 базовых метрик (η1, η2, N1, N2, f1j, f2i)
  - 3 главных метрики (η, N, V)
  - Дополнительные метрики (N^, V*, L, D, E, T, B)
"""

import sys
import os
import re
import math
from collections import Counter
from typing import Dict, List, Tuple, Any

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


class PerlHalsteadAnalyzer:
    """Класс для токенизации и расчета метрик Холстеда Perl-кода."""

    def __init__(self):
        # Служебные слова и встроенные функции Perl (словарные операторы)
        self.word_operators = {
            'and', 'or', 'not', 'xor', 'eq', 'ne', 'lt', 'gt', 'le', 'ge', 'cmp',
            'if', 'unless', 'elsif', 'else', 'for', 'foreach', 'while', 'until', 'do',
            'continue', 'last', 'next', 'redo', 'goto', 'return', 'sub', 'package',
            'use', 'require', 'my', 'our', 'local', 'state', 'defined', 'undef',
            'eval', 'die', 'warn', 'say', 'print', 'printf', 'open', 'close', 'read',
            'write', 'push', 'pop', 'shift', 'unshift', 'splice', 'split', 'join',
            'map', 'grep', 'sort', 'reverse', 'keys', 'values', 'each', 'exists',
            'delete', 'ref', 'bless', 'tie', 'untie', 'chomp', 'chop', 'length',
            'substr', 'abs', 'sqrt', 'int', 'rand', 'time', 'exit'
        }

        # Ключевые слова управляющих конструкций
        self.control_keywords = {
            'if', 'unless', 'elsif', 'else', 'for', 'foreach', 'while', 'until',
            'do', 'sub', 'given', 'when', 'my', 'our', 'local', 'state'
        }

        # Символьные операторы и знаки операций Perl
        self.symbol_operators = [
            '**=', '<<=', '>>=', '||=', '&&=', '//=', '<=>', '...', '->', '=>',
            '++', '--', '==', '!=', '<=', '>=', '&&', '||', '//', '<<', '>>',
            '+=', '-=', '*=', '/=', '%=', '.=', 'x=', '&=', '|=', '^=', '=~', '!~',
            '..', '~~', '**', '+', '-', '*', '/', '%', '=', '<', '>', '!', '&',
            '|', '^', '~', '.', 'x', '?', ':', ';', ',', '\\'
        ]

    def tokenize(self, code: str) -> List[Tuple[str, str]]:
        """Токенизация Perl-кода на основе регулярных выражений."""
        token_specification = [
            ('COMMENT',    r'#.*'),
            ('STRING',     r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`|q[qwxr]?\s*\/[^\/]*\/|q[qwxr]?\s*\{[^{}]*\}|q[qwxr]?\s*\([^()]*\)'),
            ('REGEX',      r'(?:s|tr|y)\/[^\/]*\/[^\/]*\/[a-z]*|m\/[^\/]*\/[a-z]*'),
            ('VARIABLE',   r'[\$@%]\#?\{?[a-zA-Z_][a-zA-Z0-9_]*\}?|\$\d+|\$_|@_|%ENV|\$!|\$@|\$\?|\$\$$\$/|$\\'),
            ('FLOAT',      r'\b\d+\.\d+(?:[eE][+-]?\d+)?\b|\b\.\d+(?:[eE][+-]?\d+)?\b'),
            ('HEX_BIN',    r'\b0[xBxb][0-9a-fA-F]+\b'),
            ('INT',        r'\b\d+\b'),
            ('SYM_OP',     '|'.join([re.escape(op) for op in sorted(self.symbol_operators, key=len, reverse=True)])),
            ('BRACKET',    r'[\(\)\{\}\[\]]'),
            ('WORD',       r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),
            ('SKIP',       r'\s+'),
            ('MISC',       r'.'),
        ]

        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_specification)
        
        raw_tokens = []
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            val = mo.group()
            if kind in ('SKIP', 'COMMENT'):
                continue
            raw_tokens.append((kind, val))
            
        return raw_tokens

    def analyze(self, code: str) -> Dict[str, Any]:
        """Анализирует Perl-код и вычисляет все метрики Холстеда."""
        raw_tokens = self.tokenize(code)
        
        op_counts = Counter()
        opnd_counts = Counter()

        # Составные управляющие операторы (например, do...until, if...else)
        keywords_sequence = [val for kind, val in raw_tokens if kind == 'WORD' and val in {'do', 'until', 'while', 'if', 'else', 'elsif'}]
        
        has_do = 'do' in keywords_sequence
        has_until = 'until' in keywords_sequence
        has_while = 'while' in keywords_sequence
        has_if = 'if' in keywords_sequence
        has_else = 'else' in keywords_sequence
        has_elsif = 'elsif' in keywords_sequence

        compound_handled = set()
        if has_do and has_until:
            op_counts['do...until'] += 1
            compound_handled.add('do')
            compound_handled.add('until')
        elif has_do and has_while:
            op_counts['do...while'] += 1
            compound_handled.add('do')
            compound_handled.add('while')

        if has_if and has_elsif and has_else:
            op_counts['if...elsif...else'] += 1
            compound_handled.add('if')
            compound_handled.add('elsif')
            compound_handled.add('else')
        elif has_if and has_else:
            op_counts['if...else'] += 1
            compound_handled.add('if')
            compound_handled.add('else')

        # Стек для учета скобок: True = скобка относится к вызову функции/конструкции, False = скобка приоритета вычислений
        paren_stack = []
        standalone_parens_count = 0

        open_braces, close_braces = 0, 0
        open_brackets, close_brackets = 0, 0

        i = 0
        n_tokens = len(raw_tokens)

        while i < n_tokens:
            kind, val = raw_tokens[i]

            if kind == 'WORD':
                is_followed_by_paren = (i + 1 < n_tokens and raw_tokens[i+1][1] == '(')

                if val in compound_handled:
                    pass
                elif val in self.word_operators:
                    if is_followed_by_paren:
                        if val in self.control_keywords:
                            op_counts[val] += 1
                        else:
                            op_counts[f"{val}()"] += 1
                    else:
                        op_counts[val] += 1
                else:
                    if is_followed_by_paren:
                        op_counts[f"{val}()"] += 1
                    else:
                        opnd_counts[val] += 1

            elif kind == 'SYM_OP':
                op_counts[val] += 1

            elif kind == 'BRACKET':
                if val == '(':
                    # Если перед скобкой идет WORD (имя функции или ключевое слово), скобка синтаксическая
                    prev_kind, prev_val = raw_tokens[i-1] if i > 0 else (None, None)
                    if prev_kind == 'WORD':
                        paren_stack.append(True)   # Скобка относится к вызову функции
                    else:
                        paren_stack.append(False)  # Скобка приоритета вычислений
                        standalone_parens_count += 1
                elif val == ')':
                    if paren_stack:
                        paren_stack.pop()
                elif val == '{': open_braces += 1
                elif val == '}': close_braces += 1
                elif val == '[': open_brackets += 1
                elif val == ']': close_brackets += 1

            elif kind in ('STRING', 'FLOAT', 'HEX_BIN', 'INT'):
                opnd_counts[val] += 1
            elif kind == 'VARIABLE':
                opnd_counts[val] += 1
            elif kind == 'REGEX':
                reg_op = val.split('/')[0] if '/' in val else val
                op_counts[reg_op] += 1
            elif kind == 'MISC':
                op_counts[val] += 1

            i += 1

        # Скобки приоритета вычислений () учитываются как отдельный оператор ()
        if standalone_parens_count > 0:
            op_counts['()'] = standalone_parens_count

        if open_braces > 0 or close_braces > 0:
            op_counts['{}'] = max(open_braces, close_braces)
        if open_brackets > 0 or close_brackets > 0:
            op_counts['[]'] = max(open_brackets, close_brackets)

        # 1. БАЗОВЫЕ МЕТРИКИ
        eta1 = len(op_counts)       # η1 - уникальные операторы
        eta2 = len(opnd_counts)     # η2 - уникальные операнды
        N1 = sum(op_counts.values()) # N1 - всего операторов
        N2 = sum(opnd_counts.values()) # N2 - всего операндов

        # 2. ГЛАВНЫЕ МЕТРИКИ
        eta = eta1 + eta2           # η - словарь программы
        N = N1 + N2                 # N - длина программы
        V = N * math.log2(eta) if eta > 0 else 0  # V - объем программы (в битах)

        # 3. ДОПОЛНИТЕЛЬНЫЕ МЕТРИКИ
        N_hat = (eta1 * math.log2(eta1) if eta1 > 0 else 0) + (eta2 * math.log2(eta2) if eta2 > 0 else 0)
        eta2_star = eta2
        V_star = (2 + eta2_star) * math.log2(2 + eta2_star) if (2 + eta2_star) > 0 else 0
        L = (2 / eta1) * (eta2 / N2) if eta1 > 0 and N2 > 0 else 0
        D = 1 / L if L > 0 else 0
        E = D * V
        T = E / 18
        B = V / 3000

        return {
            'op_counts': op_counts,
            'opnd_counts': opnd_counts,
            'eta1': eta1,
            'eta2': eta2,
            'N1': N1,
            'N2': N2,
            'eta': eta,
            'N': N,
            'N_hat': N_hat,
            'V': V,
            'V_star': V_star,
            'L': L,
            'D': D,
            'E': E,
            'T': T,
            'B': B
        }


# ============================================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (GUI на Tkinter)
# ============================================================================

class HalsteadGUIApp:
    """Класс графического интерфейса с окном ввода и таблицами вывода результатов."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Анализатор метрик Холстеда для кода Perl")
        self.root.geometry("1150x820")
        self.root.minsize(950, 680)
        
        self.analyzer = PerlHalsteadAnalyzer()
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

        title_label = ttk.Label(header_frame, text="Расчёт базовых и производных метрик Холстеда (Perl)", style="Title.TLabel")
        title_label.pack(side=tk.LEFT, padx=(0, 10))

        btn_bar = ttk.Frame(header_frame)
        btn_bar.pack(side=tk.RIGHT)

        ttk.Button(btn_bar, text="📁 Открыть файл...", command=self._load_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✨ Пример кода (Sin1)", command=self._insert_example).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="🗑 Очистить", command=self._clear_input).pack(side=tk.LEFT, padx=3)

        # 2. Разделитель верхнего текстового поля и нижних таблиц
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 2.1 Верхняя секция: Текстовое поле для ввода кода
        input_frame = ttk.LabelFrame(paned, text=" Исходный код Perl ", padding=5)
        paned.add(input_frame, weight=1)

        self.text_code = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        self.text_code.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        btn_run = tk.Button(
            input_frame,
            text="▶ РАССЧИТАТЬ МЕТРИКИ ХОЛСТЕДА",
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

        # 2.2 Нижняя секция: Две параллельные таблицы и выводимые метрики
        results_frame = ttk.LabelFrame(paned, text=" Результаты расчета (Таблицы Холстеда) ", padding=5)
        paned.add(results_frame, weight=2)

        tables_paned = ttk.PanedWindow(results_frame, orient=tk.HORIZONTAL)
        tables_paned.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Левая таблица: Операторы
        op_frame = ttk.Frame(tables_paned)
        tables_paned.add(op_frame, weight=1)

        ttk.Label(op_frame, text="Таблица 1. Операторы программы", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 2))
        
        self.tree_op = ttk.Treeview(op_frame, columns=("j", "operator", "f1j"), show="headings", height=8)
        self.tree_op.heading("j", text="j")
        self.tree_op.heading("operator", text="Оператор")
        self.tree_op.heading("f1j", text="f1j (частота)")
        self.tree_op.column("j", width=45, anchor=tk.CENTER)
        self.tree_op.column("operator", width=190, anchor=tk.W)
        self.tree_op.column("f1j", width=110, anchor=tk.CENTER)
        
        op_scroll = ttk.Scrollbar(op_frame, orient=tk.VERTICAL, command=self.tree_op.yview)
        self.tree_op.configure(yscrollcommand=op_scroll.set)
        
        self.tree_op.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        op_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Правая таблица: Операнды
        opnd_frame = ttk.Frame(tables_paned)
        tables_paned.add(opnd_frame, weight=1)

        ttk.Label(opnd_frame, text="Таблица 2. Операнды программы", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 2))
        
        self.tree_opnd = ttk.Treeview(opnd_frame, columns=("i", "operand", "f2i"), show="headings", height=8)
        self.tree_opnd.heading("i", text="i")
        self.tree_opnd.heading("operand", text="Операнд")
        self.tree_opnd.heading("f2i", text="f2i (частота)")
        self.tree_opnd.column("i", width=45, anchor=tk.CENTER)
        self.tree_opnd.column("operand", width=190, anchor=tk.W)
        self.tree_opnd.column("f2i", width=110, anchor=tk.CENTER)
        
        opnd_scroll = ttk.Scrollbar(opnd_frame, orient=tk.VERTICAL, command=self.tree_opnd.yview)
        self.tree_opnd.configure(yscrollcommand=opnd_scroll.set)
        
        self.tree_opnd.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        opnd_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Панель вывода итоговых метрик
        summary_frame = ttk.Frame(results_frame)
        summary_frame.pack(fill=tk.X, pady=5)

        self.lbl_base_sum = ttk.Label(summary_frame, text="η1 = 0 | N1 = 0                    η2 = 0 | N2 = 0", font=("Consolas", 11, "bold"))
        self.lbl_base_sum.pack(fill=tk.X)

        self.lbl_main_metrics = ttk.Label(summary_frame, text="Словарь программы η = 0  |  Длина N = 0  |  Объём V = 0.00 бит", style="MetricMain.TLabel")
        self.lbl_main_metrics.pack(fill=tk.X, pady=(2, 2))

        self.lbl_ext_metrics = ttk.Label(
            summary_frame,
            font=("Segoe UI", 9),
            text="N^ = 0 | V* = 0 бит | L = 0 | D = 0 | E = 0 | T = 0 сек | B = 0"
        )
        self.lbl_ext_metrics.pack(fill=tk.X)

        # Заполнение при старте примером Sin1
        self._insert_example()

    def _insert_example(self):
        example_code = '''# Пример вычисления sin(x) через разложение в ряд
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
            messagebox.showwarning("Предупреждение", "Введите или вставьте код Perl для анализа!")
            return

        res = self.analyzer.analyze(code)

        # Очистка прошлых данных из таблиц
        for item in self.tree_op.get_children():
            self.tree_op.delete(item)
        for item in self.tree_opnd.get_children():
            self.tree_opnd.delete(item)

        # Заполнение Таблицы 1 (Операторы)
        sorted_ops = sorted(res['op_counts'].items(), key=lambda x: (-x[1], x[0]))
        for idx, (op, count) in enumerate(sorted_ops, 1):
            self.tree_op.insert("", tk.END, values=(idx, op, count))

        # Заполнение Таблицы 2 (Операнды)
        sorted_opnds = sorted(res['opnd_counts'].items(), key=lambda x: (-x[1], x[0]))
        for idx, (opnd, count) in enumerate(sorted_opnds, 1):
            self.tree_opnd.insert("", tk.END, values=(idx, opnd, count))

        # Обновление текста итоговых метрик
        self.lbl_base_sum.config(
            text=f"η1 (операторы) = {res['eta1']} | N1 = {res['N1']}              η2 (операнды) = {res['eta2']} | N2 = {res['N2']}"
        )
        self.lbl_main_metrics.config(
            text=f"Словарь программы η = {res['eta']}  |  Длина N = {res['N']}  |  Объём V = {res['V']:.2f} бит"
        )
        self.lbl_ext_metrics.config(
            text=f"Расчетная длина N^ = {res['N_hat']:.2f}  |  Потенциальный объём V* = {res['V_star']:.2f} бит  |  Уровень L = {res['L']:.4f}\n"
                 f"Сложность D = {res['D']:.2f}  |  Усилия E = {res['E']:.2f}  |  Время T = {res['T']:.2f} сек ({res['T']/60:.2f} мин)  |  Ошибки B = {res['B']:.4f}"
        )


# ============================================================================
# ВЫВОД В КОНСОЛЬ (CLI РЕЖИМ)
# ============================================================================

def print_cli_results(results: Dict[str, Any]):
    """Выводит результаты анализа в консоль."""
    print("\n" + "=" * 72)
    print("           РАСЧЁТ МЕТРИК ХОЛСТЕДА ДЛЯ PERL-ПРОГРАММЫ")
    print("=" * 72)

    print("\nТаблица 1. Операторы программы")
    print("-" * 72)
    print(f"{'j':<6} {'Оператор':<30} {'f1j (частота)':<15}")
    print("-" * 72)
    sorted_ops = sorted(results['op_counts'].items(), key=lambda x: (-x[1], x[0]))
    for idx, (op, count) in enumerate(sorted_ops, 1):
        print(f"{idx:<6} {op:<30} {count:<15}")
    print("-" * 72)
    print(f"η1 (словарь операторов) = {results['eta1']:<10} N1 (всего операторов) = {results['N1']}")
    print("=" * 72)

    print("\nТаблица 2. Операнды программы")
    print("-" * 72)
    print(f"{'i':<6} {'Операнд':<30} {'f2i (частота)':<15}")
    print("-" * 72)
    sorted_opnds = sorted(results['opnd_counts'].items(), key=lambda x: (-x[1], x[0]))
    for idx, (opnd, count) in enumerate(sorted_opnds, 1):
        display_opnd = opnd if len(opnd) <= 28 else opnd[:25] + '...'
        print(f"{idx:<6} {display_opnd:<30} {count:<15}")
    print("-" * 72)
    print(f"η2 (словарь операндов)  = {results['eta2']:<10} N2 (всего операндов)  = {results['N2']}")
    print("=" * 72)

    print("\n" + "─" * 45)
    print("  1. БАЗОВЫЕ МЕТРИКИ ХОЛСТЕДА (6 показателей)")
    print("─" * 45)
    print(f"  1. η1  (Число уникальных операторов)    = {results['eta1']}")
    print(f"  2. η2  (Число уникальных операндов)     = {results['eta2']}")
    print(f"  3. N1  (Общее число операторов)         = {results['N1']}")
    print(f"  4. N2  (Общее число операндов)          = {results['N2']}")
    print(f"  5. f1j (Вхождения операторов j)         = детально в Таблице 1")
    print(f"  6. f2i (Вхождения операндов i)          = детально в Таблице 2")

    print("\n" + "─" * 45)
    print("  2. ГЛАВНЫЕ МЕТРИКИ ХОЛСТЕДА (3 показателя)")
    print("─" * 45)
    print(f"  1. η = η1 + η2 (Словарь программы)      = {results['eta']}")
    print(f"  2. N = N1 + N2 (Длина программы)        = {results['N']}")
    print(f"  3. V = N * log2(η) (Объём программы)    = {results['V']:.2f} бит")

    print("\n" + "─" * 45)
    print("  3. ДОПОЛНИТЕЛЬНЫЕ И РАСШИРЕННЫЕ МЕТРИКИ")
    print("─" * 45)
    print(f"  • N^ (Теоретическая/расчётная длина)    = {results['N_hat']:.2f}")
    print(f"  • V* (Потенциальный объём программы)    = {results['V_star']:.2f} бит")
    print(f"  • L  (Уровень программы)                = {results['L']:.4f}")
    print(f"  • D  (Сложность программы, 1/L)         = {results['D']:.2f}")
    print(f"  • E  (Усилия по написанию, D * V)       = {results['E']:.2f} элем. решений")
    print(f"  • T  (Время разработки, E / 18)         = {results['T']:.2f} сек. ({results['T']/60:.2f} мин.)")
    print(f"  • B  (Оценка потенциальных ошибок)      = {results['B']:.4f}")
    print("=" * 72 + "\n")


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
            analyzer = PerlHalsteadAnalyzer()
            results = analyzer.analyze(code)
            print_cli_results(results)
        else:
            print("ОШИБКА: Код не передан!")
    else:
        if HAS_TKINTER:
            root = tk.Tk()
            app = HalsteadGUIApp(root)
            root.mainloop()
        else:
            print("ОШИБКА: Модуль tkinter недоступен в данной системе!")


if __name__ == "__main__":
    main()