#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <slang.h>

// Структура для представления строки.
// Первые три поля совпадают с SLscroll_Type, поэтому список строк
// можно передавать функциям SLscroll_* через приведение типа.
typedef struct _Line
{
   struct _Line * next;
   struct _Line * prev;
   unsigned int flags;
   char * data;
}
Line;

// Номера цветовых пар (как init_pair в ncurses_example.c)
enum {
	COLOR_TEXT = 0,    // обычный текст
	COLOR_CURRENT = 1, // текущая строка
	COLOR_BAR = 2,     // заголовок и строка состояния
	COLOR_NUMBER = 3   // номера строк
};

static volatile sig_atomic_t screen_resized = 0;

static void sigwinch_handler(int sig) {
	(void)sig;
	screen_resized = 1;
	SLsignal(SIGWINCH, sigwinch_handler);
}

// Чтение файла в двусвязный список. Возвращает число строк или -1.
static int load_file(const char * path, Line ** first) {
	FILE * f = fopen(path, "r");
	if (f == NULL) {
		return -1;
	}

	Line * head = NULL;
	Line * tail = NULL;
	char * buf = NULL;
	size_t cap = 0;
	ssize_t len;
	int count = 0;

	while ((len = getline(&buf, &cap, f)) != -1) {
		// Убираем перевод строки (в том числе \r\n из Windows-файлов)
		while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r')) {
			buf[--len] = '\0';
		}

		Line * temp = malloc(sizeof(Line));
		if (temp == NULL) {
			break;
		}
		temp->next = NULL;
		temp->prev = tail;
		temp->flags = 0;
		temp->data = SLmake_nstring(buf, (unsigned int)len);

		if (tail != NULL) {
			tail->next = temp;
		} else {
			head = temp;
		}
		tail = temp;
		count++;
	}
	free(buf);
	fclose(f);

	// Пустой файл: оставляем одну пустую строку, чтобы окну было что показывать
	if (head == NULL) {
		head = calloc(1, sizeof(Line));
		head->data = SLmake_string("");
		count = 1;
	}

	*first = head;
	return count;
}

static void free_lines(Line * lines) {
	while (lines != NULL) {
		Line * del = lines;
		lines = lines->next;
		SLfree(del->data);
		free(del);
	}
}

// Пропуск n символов UTF-8 (для горизонтальной прокрутки)
static const char * skip_chars(const char * s, int n) {
	while (*s != '\0' && n > 0) {
		s++;
		while (((unsigned char)*s & 0xC0) == 0x80) {
			s++;
		}
		n--;
	}
	return s;
}

// Строка во всю ширину экрана с цветом полосы
static void draw_bar(int row, const char * text) {
	SLsmg_gotorc(row, 0);
	SLsmg_set_color(COLOR_BAR);
	SLsmg_write_string((char *)text);
	SLsmg_erase_eol();
	SLsmg_set_color(COLOR_TEXT);
}

static void draw(SLscroll_Window_Type * win, const char * path, int col_offset) {
	int rows = SLtt_Screen_Rows;
	int cols = SLtt_Screen_Cols;
	char info[256];

	// Строка 0 — заголовок, строки 1..rows-2 — рамка с текстом, rows-1 — состояние
	snprintf(info, sizeof(info), " Файл: %s", path);
	draw_bar(0, info);

	// SLscroll_find_top подбирает верхнюю строку окна так,
	// чтобы текущая строка оставалась видимой
	SLscroll_find_top(win);

	Line * line = (Line *)win->top_window_line;
	unsigned int line_no = win->line_num - win->window_row;
	for (unsigned int row = 0; row < win->nrows; row++) {
		SLsmg_gotorc(row + 2, 1);
		if (line != NULL) {
			int is_current = ((SLscroll_Type *)line == win->current_line);

			SLsmg_set_color(COLOR_NUMBER);
			SLsmg_printf("%5u ", line_no);
			SLsmg_set_color(is_current ? COLOR_CURRENT : COLOR_TEXT);
			SLsmg_write_string((char *)skip_chars(line->data, col_offset));
			// Текущая строка подсвечивается до правого края
			SLsmg_erase_eol();
			SLsmg_set_color(COLOR_TEXT);

			line = line->next;
			line_no++;
		} else {
			SLsmg_erase_eol();
		}
	}

	// Рамка рисуется после текста, чтобы длинные строки не заходили на её правый край
	SLsmg_set_color(COLOR_TEXT);
	SLsmg_draw_box(1, 0, rows - 2, cols);

	snprintf(info, sizeof(info),
		" Строка %u из %u, столбец %d | ↑↓ PgUp PgDn Home End ←→ | q — выход",
		win->line_num, win->num_lines, col_offset + 1);
	draw_bar(rows - 1, info);

	SLsmg_refresh();
}

// Пересчёт размеров окна после изменения размера терминала
static void update_window_size(SLscroll_Window_Type * win) {
	int n = SLtt_Screen_Rows - 4; // заголовок, строка состояния и две линии рамки
	win->nrows = n > 1 ? (unsigned int)n : 1;
}

int main(int argc, char * argv[]) {
	if (argc != 2) {
		fprintf(stderr, "Использование: %s <файл>\n", argv[0]);
		return 1;
	}

	// Строки загружаются до инициализации экрана, чтобы ошибку
	// можно было вывести в обычный терминал
	Line * lines = NULL;
	int count = load_file(argv[1], &lines);
	if (count < 0) {
		perror(argv[1]);
		return 1;
	}

	// Инициализация терминала для S-Lang
	SLutf8_enable(-1); // кодировка берётся из локали; нужна для кириллицы
	SLtt_get_terminfo();
	if (SLang_init_tty(-1, 0, 1) == -1 || SLkp_init() == -1 || SLsmg_init_smg() == -1) {
		fprintf(stderr, "Не удалось инициализировать терминал\n");
		free_lines(lines);
		return 1;
	}
	SLsignal(SIGWINCH, sigwinch_handler);

	// Цвета (аналог init_pair)
	SLtt_set_color(COLOR_TEXT, NULL, "lightgray", "black");
	SLtt_set_color(COLOR_CURRENT, NULL, "black", "green");
	SLtt_set_color(COLOR_BAR, NULL, "black", "cyan");
	SLtt_set_color(COLOR_NUMBER, NULL, "brown", "black");

	// Инициализация структуры, отвечающей за окно прокрутки
	SLscroll_Window_Type win;
	memset(&win, 0, sizeof(win));
	win.lines = (SLscroll_Type *)lines;
	win.current_line = (SLscroll_Type *)lines;
	win.line_num = 1;
	win.num_lines = (unsigned int)count;
	update_window_size(&win);

	int col_offset = 0;
	int running = 1;
	while (running) {
		if (screen_resized) {
			screen_resized = 0;
			SLtt_get_screen_size();
			SLsmg_reinit_smg();
			update_window_size(&win);
		}

		draw(&win, argv[1], col_offset);

		// Обработка нажатия клавиш. В отличие от slang.c двигается
		// текущая строка, а окно прокручивается вслед за ней.
		int key = SLkp_getkey();
		switch (key) {
			case 'q':
			case 'Q':
				running = 0;
				break;
			case SL_KEY_UP:
			case 'k':
				SLscroll_prev_n(&win, 1);
				break;
			case SL_KEY_DOWN:
			case 'j':
				SLscroll_next_n(&win, 1);
				break;
			case SL_KEY_PPAGE:
				SLscroll_pageup(&win);
				break;
			case SL_KEY_NPAGE:
			case ' ':
				SLscroll_pagedown(&win);
				break;
			case SL_KEY_HOME:
			case 'g':
				SLscroll_prev_n(&win, win.num_lines);
				break;
			case SL_KEY_END:
			case 'G': {
				SLscroll_next_n(&win, win.num_lines);
				// Верх окна ставим так, чтобы последняя страница была заполнена
				SLscroll_Type * top = win.current_line;
				for (unsigned int n = 1; n < win.nrows && top->prev != NULL; n++) {
					top = top->prev;
				}
				win.top_window_line = top;
				break;
			}
			case SL_KEY_LEFT:
				if (col_offset > 0) {
					col_offset -= 4;
				}
				break;
			case SL_KEY_RIGHT:
				col_offset += 4;
				break;
			default:
				// Клавиша без назначения (в т.ч. SL_KEY_ERR после SIGWINCH)
				break;
		}
	}

	// Возврат терминала в исходное состояние
	SLsmg_reset_smg();
	SLang_reset_tty();
	free_lines(lines);
	return 0;
}
