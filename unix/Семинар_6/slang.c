// compile with -lslang
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <slang.h>

// Структура для представления строки
typedef struct _Line
{
   struct _Line * next;
   struct _Line * prev;
   char * data;
}
Line;

int main() {
	// Инициализация терминала для S-Lang
	SLtt_get_terminfo();
	SLang_init_tty(-1, 0, 1);
	SLkp_init();
	SLsmg_init_smg();

	int i;
	Line * lines = NULL;
	Line * temp;
	// в оригинале было str[11], но "  String 99" занимает 11 символов + '\0'
	char str[16];
	// Заполнение строк
	for (i = 99; i > 0; i--) {
		temp = malloc(sizeof(Line));
		temp->next = lines;
		temp->prev = NULL;
		sprintf(str, "  String %d", i);
		temp->data = SLmake_string(str);
		if (lines != NULL) {
			lines->prev = temp;
		}
		lines = temp;
	}

	// Инициализация структуры, представляющей из себя проматываемое окно
	SLscroll_Window_Type Line_Window;
	memset((char*)&Line_Window, 0, sizeof(SLscroll_Window_Type));
	Line_Window.current_line = (SLscroll_Type *)lines;
	Line_Window.lines = (SLscroll_Type *)lines;
	Line_Window.line_num = 1;
	Line_Window.num_lines = 99;
	Line_Window.nrows = 10;

	Line * line;
	int row;
	// Установка цветов
	SLtt_set_color (0, NULL, "green", "black");
	SLtt_set_color (1, NULL, "black", "green");
	while (1) {
		if (Line_Window.top_window_line != NULL) {
			Line_Window.current_line = Line_Window.top_window_line;
		}

		SLscroll_find_top(&Line_Window);

		row = 0;
		line = (Line *)Line_Window.top_window_line;

		SLsmg_reverse_video();
                // Построчный вывод
		while (row < Line_Window.nrows) {
			SLsmg_gotorc(row + 1, 0);

			if (line != NULL) {
				SLsmg_write_string(line->data);
				line = line->next;
			}
			SLsmg_normal_video();
			SLsmg_erase_eol();
			row++;
		}

		// Отрисовка контура
		SLsmg_draw_box(0, 0, 12, 13);
		// Обновление экрана
		SLsmg_refresh();

		// Опредение нажатых клавиш
		switch (SLkp_getkey()) {
			case 'q':
				goto l_exit;
			case SL_KEY_UP:
				// Сдвиг текущей строки вверх
				SLscroll_prev_n(&Line_Window, 1);
				Line_Window.top_window_line = Line_Window.current_line;
				break;
			case SL_KEY_DOWN:
				// Сдвиг текущей строки вниз
				SLscroll_next_n(&Line_Window, 1);
				Line_Window.top_window_line = Line_Window.current_line;
				break;
		}
	}
l_exit:
	// Освобождение занятых структур
	while (lines != NULL) {
		Line * del = lines;
		lines = lines->next;
		SLfree(del->data); // строка создана SLmake_string
		free(del);
	}
	// Возврат настроек терминала
	SLsmg_reset_smg();
	SLang_reset_tty();
	return 0;
}