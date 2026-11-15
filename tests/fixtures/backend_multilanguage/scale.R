# Owned acceptance fixture; base R only, no jsonlite or expression evaluation.
# The frozen parameter file is exactly one JSON object: {"factor": number}.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L || args[[1]] != "--in-data" || args[[3]] != "--out-result") {
    stop("usage: scale.R --in-data input.tsv --out-result output.tsv")
}
native_path <- function(path) {
    if (.Platform$OS.type != "windows") return(path)
    path <- chartr("/", "\\", path)
    if (startsWith(path, "\\\\?\\")) return(path)
    if (grepl("^[A-Za-z]:", path)) return(paste0("\\\\?\\", path))
    if (startsWith(path, "\\\\")) return(paste0("\\\\?\\UNC\\", substring(path, 3L)))
    stop("fixture paths must be absolute")
}
parameter_path <- Sys.getenv("OPERON_PARAMETERS_FILE", unset = "")
if (!nzchar(parameter_path)) stop("missing frozen parameter JSON")
text <- paste(readLines(native_path(parameter_path), warn = FALSE, encoding = "UTF-8"), collapse = "\n")
pattern <- '^\\s*\\{\\s*"factor"\\s*:\\s*(-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\\s*\\}\\s*$'
parts <- regmatches(text, regexec(pattern, text, perl = TRUE))[[1]]
if (length(parts) != 2L) stop("parameters must contain exactly one finite numeric factor")
factor <- as.numeric(parts[[2]])
if (!is.finite(factor)) stop("factor is not finite")
memory <- suppressWarnings(as.numeric(Sys.getenv("OPERON_MEMORY_BYTES", unset = "0")))
if (!is.finite(memory) || memory <= 0) stop("missing full-process memory hint")
data <- read.delim(native_path(args[[2]]), header = TRUE, sep = "\t",
                   check.names = FALSE, stringsAsFactors = FALSE)
if (!identical(names(data), "value") || nrow(data) < 1L ||
    !is.numeric(data$value) || any(!is.finite(data$value))) stop("invalid numeric TSV")
data$value <- data$value * factor
if (any(!is.finite(data$value))) stop("nonfinite scaled value")
write.table(data, native_path(args[[4]]), sep = "\t", row.names = FALSE,
            col.names = TRUE, quote = FALSE)
