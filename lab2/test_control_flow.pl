#!/usr/bin/env perl
use strict;
use warnings;
use feature 'switch'; # Включение оператора множественного выбора given / when


# Функция 1: Тестирование всех видов циклов Perl
sub test_all_loops {
    my ($limit) = @_;
    my $sum = 0;

    # 1. Цикл for
    for (my $i = 0; $i < $limit; $i++) {
        $sum += $i;
    }
    # 2. Цикл foreach
    my @items = (10, 20, 30);
    foreach my $val (@items) {
        $sum += $val;
    }
    # 3. Цикл while
    my $w_count = 0;
    while ($w_count < 3) {
        $sum += $w_count;
        $w_count++;
    }
    # 4. Цикл until
    my $u_count = 5;
    until ($u_count <= 0) {
        $sum += $u_count;
        $u_count--;
    }
    # 5. Цикл do...until
    my $d_count = 1;
    do {
        $sum *= 2;
        $d_count++;
    } until ($d_count > 3);

    return $sum;
}

# Функция 2: Тестирование ветвлений и множественного выбора (given/when)
sub test_all_branches {
    my ($mode, $score, $flag) = @_;
    my $category = "None";

    # Условие unless
    unless ($flag) {
        return "Disabled";
    }
    # Множественный выбор (given / when / default - Switch/Case в Perl)
    given ($mode) {
        when (1) {
            $category = "Mode_1";
        }
        when (2) {
            # ПРЕДПОСЛЕДНЯЯ ветка с вложенными конструкциями (требование преподавателя)
            if ($score >= 90) {
                $category = "High_Score";
            } elsif ($score >= 75) {
                for (my $k = 0; $k < 2; $k++) {
                    $category = ($k == 0) ? "Mid_Score_A" : "Mid_Score_B";
                }
            } else {
                $category = "Low_Score";
            }
        }
        when (3) {
            $category = "Mode_3";
        }
        default {
            $category = "Mode_Default";
        }
    }
    return $category;
}

# Главная управляющая подпрограмма
sub main {
    print "=== НАЧАЛО ТЕСТИРОВАНИЯ ===\n";

    my $loop_res = test_all_loops(5);
    print "Результат циклов: $loop_res\n";

    my $cat1 = test_all_branches(2, 80, 1);
    my $cat2 = test_all_branches(4, 50, 0);
    print "Категории: $cat1, $cat2\n";

    print "=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ===\n";
}

main();
