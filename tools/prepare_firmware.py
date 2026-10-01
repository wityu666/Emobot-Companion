"""Build-time compatibility patch for the pinned WebSockets 2.6.1 dependency.

Its header unconditionally defines a 15 KB message cap. Make that default
conditional so the application's bounded 150 KB cap takes effect without
manual edits. The dependency's LGPL header and all other code are unchanged.
"""

from pathlib import Path

Import("env")  # noqa: F821 -- provided by PlatformIO/SCons
header = Path(env.subst("$PROJECT_LIBDEPS_DIR")) / env["PIOENV"] / "WebSockets/src/WebSockets.h"  # noqa: F821
if header.exists():
    source = header.read_text()
    marker = "#define WEBSOCKETS_MAX_DATA_SIZE (15 * 1024)"
    replacement = "#ifndef WEBSOCKETS_MAX_DATA_SIZE\n" + marker + "\n#endif"
    if replacement not in source:
        if marker not in source:
            raise RuntimeError(
                "Pinned WebSockets header changed; inspect before applying compatibility patch"
            )
        header.write_text(source.replace(marker, replacement))
