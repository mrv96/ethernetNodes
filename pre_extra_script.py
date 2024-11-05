import re
import shutil
from pathlib import Path

Import("env")


DATA_DIR = Path(env.subst('$PROJECT_DATA_DIR'))
BUILD_DATA_DIR = Path(env.subst('$BUILD_DIR')) / DATA_DIR.name


def rm_lib_src(libdir:str):
    lib = Path(env.get('PROJECT_LIBDEPS_DIR')) / env.get('PIOENV') / libdir
    piopm = lib / '.piopm'
    library_json = lib / 'library.json'

    if len(tuple(lib.iterdir())) <= 2:
        return

    with piopm.open() as f1, library_json.open() as f2:
        piopm_content = f1.read()
        library_json_content = f2.read()

    shutil.rmtree(str(lib), ignore_errors=True)
    lib.mkdir()

    with piopm.open('w') as f1, library_json.open('w') as f2:
        f1.write(piopm_content)
        f2.write(library_json_content)


def surround_with_ifndef(file:Path, define_name:str):
    indexes = []

    with file.open() as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if re.match(r'\s*#define\s+' + define_name, line) and \
               re.match(r'\s*#ifndef\s+' + define_name, lines[i-1]) == None:
                indexes.append(i)

    if not indexes:
        return

    for i in indexes[::-1]:
        lines.insert(i+1, '#endif\n')
        lines.insert(i, f'#ifndef {define_name}\n')

    with file.open('w') as f:
        f.write(''.join(lines))


# Remove EthernetWebServer unneeded deps to avoid build conflicts
rm_lib_src('Ethernet_Generic')


# Allow MAX_SOCK_NUM GCC define surrounding C MAX_SOCK_NUM defines with #ifndef/endif
platform = env.PioPlatform()
for package in platform.dump_used_packages():
    if 'framework' in package['name']:
        package_dir = Path(platform.get_package_dir(package['name']))
        surround_with_ifndef(package_dir/'libraries'/'Ethernet'/'src'/'Ethernet.h', 'MAX_SOCK_NUM')
        surround_with_ifndef(package_dir/'cores'/'esp8266'/'wl_definitions.h', 'MAX_SOCK_NUM')
        break


def minify_web_sources(source, target, env):
    try:
        import minify_html, rcssmin, rjsmin
    except ModuleNotFoundError:
        env.Execute("$PYTHONEXE -m pip install minify_html rcssmin rjsmin")
        import minify_html, rcssmin, rjsmin

    env.Execute(Delete(BUILD_DATA_DIR))
    BUILD_DATA_DIR.mkdir()

    for p in DATA_DIR.rglob('*.html'):
        new_p = BUILD_DATA_DIR / p.relative_to(DATA_DIR)
        new_p.write_text(
            minify_html.minify(
                p.read_text(),
                do_not_minify_doctype=True,
                ensure_spec_compliant_unquoted_attribute_values=True,
                keep_spaces_between_attributes=True,
                minify_css=True,
                minify_js=True,
            )
        )

    for p in DATA_DIR.rglob('*.css'):
        new_p = BUILD_DATA_DIR / p.relative_to(DATA_DIR)
        new_p.write_text(rcssmin.cssmin(p.read_text()))

    for p in DATA_DIR.rglob('*.js'):
        new_p = BUILD_DATA_DIR / p.relative_to(DATA_DIR)
        new_p.write_text(rjsmin.jsmin(p.read_text()))


env.Replace(PROJECT_DATA_DIR=BUILD_DATA_DIR)
env.AddPreAction("buildfs", minify_web_sources)
env.AddPreAction("uploadfs", minify_web_sources)
env.AddPreAction("uploadfsota", minify_web_sources)
