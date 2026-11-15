/* Owned acceptance fixture: one-column numeric TSV -> offset TSV.
 * Build with the adjacent CMakeLists.txt and Ninja; no recipient compiler.
 * No shell, process launch, network or scientific runtime is used.
 */
#include <errno.h>
#include <float.h>
#include <locale.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#ifdef _WIN32
#include <windows.h>
#endif

static int finite_number(double value) {
#ifdef _MSC_VER
    return _finite(value);
#else
    return isfinite(value);
#endif
}

static int transform(FILE *input, FILE *output, double offset) {
    char line[4096], *end;
    size_t rows = 0, length;
    double value;
    if (!fgets(line, sizeof(line), input)) return 10;
    line[strcspn(line, "\r\n")] = '\0';
    if (strcmp(line, "value") != 0 || fprintf(output, "value\n") < 0) return 11;
    while (fgets(line, sizeof(line), input)) {
        length = strlen(line);
        if (length == sizeof(line) - 1 && line[length - 1] != '\n') return 12;
        errno = 0;
        value = strtod(line, &end);
        if (end == line || errno == ERANGE || !finite_number(value)) return 13;
        while (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n') ++end;
        if (*end != '\0') return 14;
        value += offset;
        if (!finite_number(value) || fprintf(output, "%.17g\n", value) < 0) return 15;
        ++rows;
    }
    if (ferror(input) || rows == 0 || fflush(output) != 0) return 16;
    return 0;
}

#ifdef _WIN32
static wchar_t *extended_path(const wchar_t *path) {
    DWORD length;
    wchar_t *absolute, *result;
    size_t prefix, count;
    if (wcsncmp(path, L"\\\\?\\", 4) == 0) {
        count = wcslen(path) + 1;
        result = (wchar_t *)malloc(count * sizeof(wchar_t));
        if (result) memcpy(result, path, count * sizeof(wchar_t));
        return result;
    }
    length = GetFullPathNameW(path, 0, NULL, NULL);
    if (length == 0 || length > 32760) return NULL;
    absolute = (wchar_t *)malloc((length + 1) * sizeof(wchar_t));
    if (!absolute) return NULL;
    if (!GetFullPathNameW(path, length + 1, absolute, NULL)) {
        free(absolute);
        return NULL;
    }
    prefix = wcsncmp(absolute, L"\\\\", 2) == 0 ? 8 : 4;
    count = wcslen(absolute) + prefix + 1;
    result = (wchar_t *)malloc(count * sizeof(wchar_t));
    if (result) {
        if (prefix == 8) {
            wcscpy(result, L"\\\\?\\UNC\\");
            wcscat(result, absolute + 2);
        } else {
            wcscpy(result, L"\\\\?\\");
            wcscat(result, absolute);
        }
    }
    free(absolute);
    return result;
}

int wmain(int argc, wchar_t **argv) {
    wchar_t *input_path, *output_path, *end;
    FILE *input, *output;
    double offset;
    int result;
    setlocale(LC_NUMERIC, "C");
    if (argc == 2 && wcscmp(argv[1], L"--version") == 0) {
        puts("operon-multilang-fixture/1");
        return 0;
    }
    if (argc != 7 || wcscmp(argv[1], L"--input") || wcscmp(argv[3], L"--output") ||
        wcscmp(argv[5], L"--offset")) {
        fputs("usage: numeric_transform --input input.tsv --output output.tsv --offset number\n", stderr);
        return 2;
    }
    errno = 0;
    offset = wcstod(argv[6], &end);
    if (end == argv[6] || *end || errno == ERANGE || !finite_number(offset)) return 3;
    input_path = extended_path(argv[2]);
    output_path = extended_path(argv[4]);
    if (!input_path || !output_path) {
        free(input_path);
        free(output_path);
        return 4;
    }
    input = _wfopen(input_path, L"rb");
    output = _wfopen(output_path, L"wb");
    free(input_path);
    free(output_path);
    if (!input || !output) {
        if (input) fclose(input);
        if (output) fclose(output);
        return 5;
    }
    result = transform(input, output, offset);
    if (fclose(input) != 0 && result == 0) result = 17;
    if (fclose(output) != 0 && result == 0) result = 18;
    return result;
}
#else
int main(int argc, char **argv) {
    FILE *input, *output;
    char *end;
    double offset;
    int result;
    setlocale(LC_NUMERIC, "C");
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("operon-multilang-fixture/1");
        return 0;
    }
    if (argc != 7 || strcmp(argv[1], "--input") || strcmp(argv[3], "--output") ||
        strcmp(argv[5], "--offset")) return 2;
    errno = 0;
    offset = strtod(argv[6], &end);
    if (end == argv[6] || *end || errno == ERANGE || !finite_number(offset)) return 3;
    input = fopen(argv[2], "rb");
    output = fopen(argv[4], "wb");
    if (!input || !output) {
        if (input) fclose(input);
        if (output) fclose(output);
        return 5;
    }
    result = transform(input, output, offset);
    if (fclose(input) != 0 && result == 0) result = 17;
    if (fclose(output) != 0 && result == 0) result = 18;
    return result;
}
#endif
