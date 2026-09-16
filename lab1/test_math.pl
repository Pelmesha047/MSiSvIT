#!/usr/bin/env perl
use strict;
use warnings;

# ============================================================================
# Модуль математических вычислений и тестирования метрик Холстеда
# Файл содержит различные подпрограммы вычислений и алгоритмов
# ============================================================================

# Подпрограмма сложения массива чисел
sub sum {
    my (@numbers) = @_;
    my $total = 0;
    foreach my $num (@numbers) {
        $total += $num;
    }
    return $total;
}

# Подпрограмма вычитания аргументов из первого значения
sub subtract {
    my ($first, @rest) = @_;
    my $result = $first;
    foreach my $num (@rest) {
        $result -= $num;
    }
    return $result;
}

# Подпрограмма умножения массива чисел
sub multiply {
    my (@numbers) = @_;
    return 0 if scalar(@numbers) == 0;
    my $product = 1;
    foreach my $num (@numbers) {
        $product *= $num;
    }
    return $product;
}

# Подпрограмма деления двух чисел с проверкой деления на ноль
sub divide {
    my ($numerator, $denominator) = @_;
    if ($denominator == 0) {
        die "Ошибка: Деление на ноль недопустимо!";
    }
    return $numerator / $denominator;
}

# Подпрограмма возведения в степень
sub power {
    my ($base, $exponent) = @_;
    my $result = 1;
    my $count = 0;
    while ($count < $exponent) {
        $result *= $base;
        $count++;
    }
    return $result;
}

# Подпрограмма вычисления факториала
sub factorial {
    my ($n) = @_;
    return 1 if $n <= 1;
    my $fact = 1;
    for (my $i = 2; $i <= $n; $i++) {
        $fact *= $i;
    }
    return $fact;
}

# Подпрограмма проверки числа на простоту
sub is_prime {
    my ($number) = @_;
    return 0 if $number <= 1;
    my $i = 2;
    while ($i * $i <= $number) {
        if ($number % $i == 0) {
            return 0;
        }
        $i++;
    }
    return 1;
}

# Подпрограмма вычисления Наибольшего Общего Делителя (НОД)
sub gcd {
    my ($a, $b) = @_;
    while ($b != 0) {
        my $temp = $b;
        $b = $a % $b;
        $a = $temp;
    }
    return $a;
}

# Подпрограмма вычисления Наименьшего Общего Кратного (НОК)
sub lcm {
    my ($a, $b) = @_;
    return 0 if $a == 0 || $b == 0;
    my $gcd_val = gcd($a, $b);
    return abs($a * $b) / $gcd_val;
}

# Подпрограмма вычисления среднего арифметического
sub average {
    my (@values) = @_;
    my $count = scalar(@values);
    return 0 if $count == 0;
    my $total = sum(@values);
    return $total / $count;
}

# Подпрограмма вычисления дисперсии массива чисел
sub variance {
    my (@values) = @_;
    my $n = scalar(@values);
    return 0 if $n <= 1;
    my $avg = average(@values);
    my $sum_sq_diff = 0;
    foreach my $x (@values) {
        my $diff = $x - $avg;
        $sum_sq_diff += $diff * $diff;
    }
    return $sum_sq_diff / ($n - 1);
}

# Подпрограмма вычисления ряда Тейлора для синуса
sub calculate_sin {
    my ($x, $terms) = @_;
    my $sin_val = 0;
    for (my $n = 0; $n < $terms; $n++) {
        my $sign = ($n % 2 == 0) ? 1 : -1;
        my $num = power($x, 2 * $n + 1);
        my $den = factorial(2 * $n + 1);
        $sin_val += $sign * ($num / $den);
    }
    return $sin_val;
}

# Главная управляющая подпрограмма для тестирования всех вычислений
sub run_all_tests {
    print "=== НАЧАЛО ТЕСТИРОВАНИЯ ВЫЧИСЛИТЕЛЬНЫХ МЕТОДОВ ===\n";

    my @data = (10, 20, 30, 40, 50);
    my $s = sum(@data);
    print "Сумма: $s\n";

    my $m = multiply(@data);
    print "Произведение: $m\n";

    my $sub_res = subtract(100, 20, 15, 5);
    print "Результат вычитания: $sub_res\n";

    my $div_res = divide(100, 4);
    print "Результат деления: $div_res\n";

    my $pow_res = power(2, 10);
    print "2^10 = $pow_res\n";

    my $fact_5 = factorial(5);
    print "5! = $fact_5\n";

    my $check_num = 29;
    my $prime_flag = is_prime($check_num);
    if ($prime_flag == 1) {
        print "Число $check_num является простым\n";
    } else {
        print "Число $check_num не является простым\n";
    }

    my $g = gcd(48, 18);
    my $l = lcm(48, 18);
    print "НОД(48, 18) = $g, НОК(48, 18) = $l\n";

    my $avg_val = average(@data);
    my $var_val = variance(@data);
    print "Среднее: $avg_val, Дисперсия: $var_val\n";

    my $angle = 0.523598; # ~30 градусов в радианах
    my $sin_approx = calculate_sin($angle, 5);
    print "Sin(0.523598) ~= $sin_approx\n";

    print "=== ТЕСТИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО ===\n";
}

# Вызов главной подпрограммы
run_all_tests();
