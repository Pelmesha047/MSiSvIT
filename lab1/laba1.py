#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Парсер и анализатор метрик Холстеда для кода на языке Perl.
Анализирует исходный код Perl и вычисляет:
  - 6 базовых метрик (η1, η2, N1, N2, f1j, f2i)
  - 3 главных метрики (η, N, V)
  - Дополнительные метрики (N^, V*, L, D, E, T, B)
"""

import sys
import re
import math
from collections import Counter
from typing import Dict, List, Tuple, Any

# Настройка UTF-8 для корректного вывода в консоль (в т.ч. под Windows)
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

        # Символьные операторы и знаки операций Perl
        self.symbol_operators = [
            '**=', '<<=', '>>=', '||=', '&&=', '//=', '<=>', '...', '->', '=>',
            '++', '--', '==', '!=', '<=', '>=', '&&', '||', '//', '<<', '>>',
            '+=', '-=', '*=', '/=', '%=', '.=', 'x=', '&=', '|=', '^=', '=~', '!~',
            '..', '~~', '**', '+', '-', '*', '/', '%', '=', '<', '>', '!', '&',
            '|', '^', '~', '.', 'x', '?', ':', ';', ',', '\\'
        ]

    def tokenize(self, code: str) -> List[Tuple[str, str]]:
        """
        Токенизация Perl-кода на основе регулярных выражений.
        Удаляет комментарии, сохраняя символ '#' внутри строковых литералов.
        """
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

        open_parens, close_parens = 0, 0
        open_braces, close_braces = 0, 0
        open_brackets, close_brackets = 0, 0

        # Определение составных управляющих операторов (например, do...until, if...else)
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

        i = 0
        n_tokens = len(raw_tokens)

        while i < n_tokens:
            kind, val = raw_tokens[i]

            if kind == 'WORD':
                if val in compound_handled:
                    pass  # Ранее учтено в составном операторе
                elif val in self.word_operators:
                    if i + 1 < n_tokens and raw_tokens[i+1][1] == '(':
                        op_counts[f"{val}()"] += 1
                    else:
                        op_counts[val] += 1
                else:
                    if i + 1 < n_tokens and raw_tokens[i+1][1] == '(':
                        op_counts[f"{val}()"] += 1
                    else:
                        opnd_counts[val] += 1
            elif kind == 'SYM_OP':
                op_counts[val] += 1
            elif kind == 'BRACKET':
                if val == '(': open_parens += 1
                elif val == ')': close_parens += 1
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

        # Сведение скобок в операторы пар скобок
        if open_parens > 0 or close_parens > 0:
            op_counts['()'] = max(open_parens, close_parens)
        if open_braces > 0 or close_braces > 0:
            op_counts['{}'] = max(open_braces, close_braces)
        if open_brackets > 0 or close_brackets > 0:
            op_counts['[]'] = max(open_brackets, close_brackets)

        # 1. БАЗОВЫЕ МЕТРИКИ (6 базовых показателей)
        eta1 = len(op_counts)       # η1 - словарь операторов (число уникальных операторов)
        eta2 = len(opnd_counts)     # η2 - словарь операндов (число уникальных операндов)
        N1 = sum(op_counts.values()) # N1 - общее число операторов
        N2 = sum(opnd_counts.values()) # N2 - общее число операндов
        # f1j - вхождения j-го оператора (op_counts)
        # f2i - вхождения i-го операнда (opnd_counts)

        # 2. ГЛАВНЫЕ МЕТРИКИ (3 производных показателя)
        eta = eta1 + eta2           # η - словарь программы
        N = N1 + N2                 # N - длина программы
        V = N * math.log2(eta) if eta > 0 else 0  # V - объем программы (в битах)

        # 3. ДОПОЛНИТЕЛЬНЫЕ РАСШИРЕННЫЕ МЕТРИКИ
        N_hat = (eta1 * math.log2(eta1) if eta1 > 0 else 0) + (eta2 * math.log2(eta2) if eta2 > 0 else 0) # N^ - расчетная длина
        eta2_star = eta2
        V_star = (2 + eta2_star) * math.log2(2 + eta2_star) if (2 + eta2_star) > 0 else 0 # V* - потенциальный объем
        L = (2 / eta1) * (eta2 / N2) if eta1 > 0 and N2 > 0 else 0 # L - уровень программы
        D = 1 / L if L > 0 else 0   # D - сложность программы
        E = D * V                    # E - трудоемкость (усилия на разработку)
        T = E / 18                   # T - время разработки в секундах
        B = V / 3000                 # B - прогнозируемое количество ошибок

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


def print_results(results: Dict[str, Any]):
    """Выводит результаты анализа в виде форматированных таблиц и метрик."""
    print("\n" + "=" * 72)
    print("           РАСЧЁТ МЕТРИК ХОЛСТЕДА ДЛЯ PERL-ПРОГРАММЫ")
    print("=" * 72)

    # Таблица 1: Операторы
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

    # Таблица 2: Операнды
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

    # Раздел 1: 6 Базовых метрик
    print("\n" + "─" * 45)
    print("  1. БАЗОВЫЕ МЕТРИКИ ХОЛСТЕДА (6 показателей)")
    print("─" * 45)
    print(f"  1. η1  (Число уникальных операторов)    = {results['eta1']}")
    print(f"  2. η2  (Число уникальных операндов)     = {results['eta2']}")
    print(f"  3. N1  (Общее число операторов)         = {results['N1']}")
    print(f"  4. N2  (Общее число операндов)          = {results['N2']}")
    print(f"  5. f1j (Вхождения операторов j)         = детально в Таблице 1")
    print(f"  6. f2i (Вхождения операндов i)          = детально в Таблице 2")

    # Раздел 2: 3 Главные метрики
    print("\n" + "─" * 45)
    print("  2. ГЛАВНЫЕ МЕТРИКИ ХОЛСТЕДА (3 показателя)")
    print("─" * 45)
    print(f"  1. η = η1 + η2 (Словарь программы)      = {results['eta']}")
    print(f"  2. N = N1 + N2 (Длина программы)        = {results['N']}")
    print(f"  3. V = N * log2(η) (Объём программы)    = {results['V']:.2f} бит")

    # Раздел 3: Дополнительные расширенные метрики
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
    """Главная точка входа в программу."""
    code = ""
    
    # 1. Передача пути к файлу через аргумент командной строки
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            print(f"[+] Успешно прочитан файл: {filepath}")
        except Exception as e:
            print(f"[-] Ошибка при чтении файла {filepath}: {e}")
            sys.exit(1)
            
    # 2. Передача кода через конвейер stdin (pipe / redirect)
    elif not sys.stdin.isatty():
        code = sys.stdin.read()
        
    # 3. Интерактивный режим ввода через консоль
    else:
        print("=" * 72)
        print("        АНАЛИЗАТОР МЕТРИК ХОЛСТЕДА ДЛЯ КОДА PERL")
        print("=" * 72)
        print("\nИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ:")
        print("1. Запуск с файлом:      python laba1.py <путь_к_файлу.pl>")
        print("2. Или введите код Perl прямо в консоль.")
        print("3. Завершите ввод словом 'END' на отдельной строке или Ctrl+Z (Ctrl+D).")
        print("-" * 72)
        print("ВВЕДИТЕ КОД PERL (для завершения наберите END):")
        print("-" * 72)

        lines = []
        try:
            while True:
                line = input()
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
        except EOFError:
            pass
        except KeyboardInterrupt:
            print("\nВвод прерван пользователем.")
            return

        code = '\n'.join(lines)

    if not code.strip():
        print("ОШИБКА: Исходный код Perl не введён!")
        return

    analyzer = PerlHalsteadAnalyzer()
    try:
        results = analyzer.analyze(code)
        print_results(results)
    except Exception as e:
        print(f"ОШИБКА при анализе кода: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()