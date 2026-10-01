#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Графическое приложение (GUI) и CLI-анализатор МЕТРИКИ ДЖИЛБА для кода на языке Perl.

Вычисляемые показатели метрики Джилба:
1. CL — Абсолютная сложность программы (количество условных операторов и операторов выбора)
2. cl — Относительная сложность программы (отношение CL к общему количеству операторов)
3. CLI — Максимальный уровень вложенности условных операторов и циклов
"""

import sys
import os
import re
from typing import Dict, List, Tuple, Any, Optional

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


class PerlGilbAnalyzer:
    """Анализатор метрики Джилба для исходного кода на Perl."""

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

        tokens = []
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'NEWLINE':
                line_num += 1
                continue
            elif kind in ('SKIP', 'COMMENT'):
                continue
            
            tokens.append({
                'kind': kind,
                'value': value,
                'line': line_num
            })

        return tokens

    def analyze(self, code: str) -> Dict[str, Any]:
        """Расчет метрики Джилба: CL, cl, CLI."""
        tokens = self.tokenize(code)

        lines = code.splitlines()
        statement_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
        total_statements = len(statement_lines) if statement_lines else 1

        cl_count = 0
        max_cli = 0
        in_code_nesting = 0
        
        block_stack = []
        gilb_details = []

        i = 0
        n_tokens = len(tokens)

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
                    block_stack.pop()
                i += 1
                continue

            # Условный оператор IF / ELSIF / UNLESS
            if kind == 'WORD' and val in ('if', 'elsif', 'unless'):
                is_postfix = False
                if i > 0 and tokens[i-1]['value'] not in (';', '{', '}', 'do'):
                    is_postfix = True

                cl_count += 1

                # Учет уровня вложенности для цепочек разветвлений (elsif)
                effective_nesting = in_code_nesting
                if val == 'elsif' and block_stack:
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

                block_stack.append({
                    'type': val,
                    'brace_depth': in_code_nesting + 1,
                    'chain_depth': 0
                })

            # Конструкция ELSE
            elif kind == 'WORD' and val == 'else':
                if block_stack and block_stack[-1]['type'] in ('if', 'elsif', 'unless'):
                    last_b = block_stack[-1]
                    effective_nesting = in_code_nesting + last_b.get('chain_depth', 0) + 1
                    if effective_nesting > max_cli:
                        max_cli = effective_nesting

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

                block_stack.append({
                    'type': val,
                    'brace_depth': in_code_nesting + 1,
                    'chain_depth': 0
                })

            # Тернарный оператор ? :
            elif val == '?':
                cl_count += 1
                effective_nesting = in_code_nesting
                if effective_nesting > max_cli:
                    max_cli = effective_nesting

                gilb_details.append({
                    'line': line,
                    'operator': '?:',
                    'type': 'Тернарный оператор выбора',
                    'nesting': effective_nesting
                })

            # Разветвления GIVEN / WHEN / DEFAULT (Switch / Case)
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

            elif kind == 'WORD' and val == 'given':
                block_stack.append({
                    'type': 'given',
                    'brace_depth': in_code_nesting + 1,
                    'chain_depth': 0
                })

            i += 1

        cl_relative = (cl_count / total_statements) if total_statements > 0 else 0.0

        return {
            'CL': cl_count,
            'cl': cl_relative,
            'CLI': max_cli,
            'total_statements': total_statements,
            'details': gilb_details
        }


# ============================================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (GUI на Tkinter)
# ============================================================================

class GilbGUIApp:
    """Класс графического интерфейса пользователя (GUI) для метрики Джилба."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Анализатор Метрики Джилба (Perl)")
        self.root.geometry("1100x780")
        self.root.minsize(900, 620)

        self.analyzer = PerlGilbAnalyzer()
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground="#1a365d")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1a365d")
        style.configure("MetricMain.TLabel", font=("Consolas", 12, "bold"), foreground="#1a365d")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", font=("Consolas", 10), rowheight=24)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Верхняя панель: Заголовок и кнопки управления
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = ttk.Label(
            header_frame,
            text="Расчет Метрики Джилба (CL, cl, CLI) для Perl",
            style="Title.TLabel"
        )
        title_label.pack(side=tk.LEFT, padx=(0, 10))

        btn_bar = ttk.Frame(header_frame)
        btn_bar.pack(side=tk.RIGHT)

        ttk.Button(btn_bar, text="📁 Открыть файл...", command=self._load_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✨ Загрузить пример", command=self._insert_example).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="🗑 Очистить", command=self._clear_input).pack(side=tk.LEFT, padx=3)

        # 2. Разделитель верхнего текстового поля и нижней таблицы
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 2.1 Верхняя секция: Редактор кода Perl
        input_frame = ttk.LabelFrame(paned, text=" Исходный код Perl для анализа ", padding=6)
        paned.add(input_frame, weight=1)

        self.text_code = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        self.text_code.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        btn_run = tk.Button(
            input_frame,
            text="▶ РАССЧИТАТЬ МЕТРИКУ ДЖИЛБА",
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
        btn_run.pack(fill=tk.X, pady=(6, 0))

        # 2.2 Нижняя секция: Результаты Джилба
        results_frame = ttk.LabelFrame(paned, text=" Результаты анализа (Метрика Джилба) ", padding=8)
        paned.add(results_frame, weight=2)

        # Панель вывода 3-х ключевых показателей Джилба
        cards_frame = ttk.Frame(results_frame)
        cards_frame.pack(fill=tk.X, pady=(0, 10))

        # 1. Абсолютная сложность CL
        card1 = ttk.LabelFrame(cards_frame, text=" 1. Абсолютная сложность (CL) ", padding=8)
        card1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.lbl_cl = ttk.Label(card1, text="CL = 0", font=("Segoe UI", 16, "bold"), foreground="#2b6cb0", anchor=tk.CENTER)
        self.lbl_cl.pack(fill=tk.BOTH, expand=True)

        # 2. Относительная сложность cl
        card2 = ttk.LabelFrame(cards_frame, text=" 2. Относительная сложность (cl) ", padding=8)
        card2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.lbl_cl_rel = ttk.Label(card2, text="cl = 0.000 (0.0%)", font=("Segoe UI", 16, "bold"), foreground="#276749", anchor=tk.CENTER)
        self.lbl_cl_rel.pack(fill=tk.BOTH, expand=True)

        # 3. Максимальный уровень вложенности CLI
        card3 = ttk.LabelFrame(cards_frame, text=" 3. Макс. вложенность (CLI) ", padding=8)
        card3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.lbl_cli = ttk.Label(card3, text="CLI = 0", font=("Segoe UI", 16, "bold"), foreground="#c53030", anchor=tk.CENTER)
        self.lbl_cli.pack(fill=tk.BOTH, expand=True)

        # Таблица операторов условного выбора Джилба
        ttk.Label(results_frame, text="Детализация операторов условного выбора и их вложенности:", style="Header.TLabel").pack(anchor=tk.W, pady=(4, 4))

        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree_gilb = ttk.Treeview(
            tree_frame,
            columns=("idx", "line", "op", "type", "nesting"),
            show="headings",
            height=10
        )
        self.tree_gilb.heading("idx", text="№")
        self.tree_gilb.heading("line", text="Строка")
        self.tree_gilb.heading("op", text="Оператор выбора")
        self.tree_gilb.heading("type", text="Категория конструкта")
        self.tree_gilb.heading("nesting", text="Уровень вложенности (CLI)")

        self.tree_gilb.column("idx", width=60, anchor=tk.CENTER)
        self.tree_gilb.column("line", width=90, anchor=tk.CENTER)
        self.tree_gilb.column("op", width=180, anchor=tk.W)
        self.tree_gilb.column("type", width=420, anchor=tk.W)
        self.tree_gilb.column("nesting", width=200, anchor=tk.CENTER)

        gilb_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_gilb.yview)
        self.tree_gilb.configure(yscrollcommand=gilb_scroll.set)

        self.tree_gilb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        gilb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._setup_treeview_copy(self.tree_gilb)

        # Загрузка тестового примера при старте
        self._insert_example()

    def _insert_example(self):
        try:
            with open(r'd:\Документы\Уник\Метра\lab2\test_control_flow.pl', 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            self.text_code.delete("1.0", tk.END)
            self.text_code.insert(tk.END, code)
            self._analyze_code()
        except Exception:
            pass

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

        # Очистка прошлых данных из таблицы
        for item in self.tree_gilb.get_children():
            self.tree_gilb.delete(item)

        # Заполнение таблицы
        for idx, item in enumerate(res['details'], 1):
            self.tree_gilb.insert("", tk.END, values=(
                idx,
                item['line'],
                item['operator'],
                item['type'],
                item['nesting']
            ))

        # Обновление блоков карточек Джилба
        self.lbl_cl.config(text=f"CL = {res['CL']}")
        self.lbl_cl_rel.config(text=f"cl = {res['cl']:.4f} ({res['cl']*100:.1f}%)")
        self.lbl_cli.config(text=f"CLI = {res['CLI']}")

    def _setup_treeview_copy(self, tree: ttk.Treeview):
        """Настройка копирования по Ctrl+C и через контекстное меню."""
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
    """Выводит ИСКЛЮЧИТЕЛЬНО метрику Джилба в консоль."""
    print("\n" + "=" * 75)
    print("                    РАСЧЁТ МЕТРИКИ ДЖИЛБА (PERL)")
    print("=" * 75)

    print("\nДетализация операторов условного выбора и их вложенности:")
    print("-" * 75)
    print(f"{'№':<5} {'Строка':<8} {'Оператор':<18} {'Категория':<32} {'CLI':<8}")
    print("-" * 75)
    for idx, item in enumerate(results['details'], 1):
        print(f"{idx:<5} {item['line']:<8} {item['operator']:<18} {item['type']:<32} {item['nesting']:<8}")
    print("-" * 75)

    print("\n" + "─" * 50)
    print("  ИТОГОВЫЕ ПОКАЗАТЕЛИ МЕТРИКИ ДЖИЛБА")
    print("─" * 50)
    print(f"  1. Абсолютная сложность (CL)       = {results['CL']}")
    print(f"  2. Относительная сложность (cl)     = {results['cl']:.4f} ({results['cl']*100:.2f}%)")
    print(f"  3. Макс. уровень вложенности (CLI)  = {results['CLI']}")
    print(f"  •  Всего операторов программы (N)  = {results['total_statements']}")
    print("=" * 75 + "\n")


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
            analyzer = PerlGilbAnalyzer()
            results = analyzer.analyze(code)
            print_cli_results(results)
        else:
            print("ОШИБКА: Код не передан!")
    else:
        if HAS_TKINTER:
            root = tk.Tk()
            app = GilbGUIApp(root)
            root.mainloop()
        else:
            print("ОШИБКА: Модуль tkinter недоступен в данной системе!")


if __name__ == "__main__":
    main()
