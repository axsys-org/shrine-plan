
/** Turns a nat value that is valid ascii into a string, returns NULL if not
 * string */
char* pl_nat_to_cstr(const ax_allocator* loc, pl_val val);

/** Checks if value is str */
bool pl_nat_is_str(pl_val v);
