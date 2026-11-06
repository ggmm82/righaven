"""Runtime installer adapter: distinguish packaged CLIs from shell completions.

Keep the immutable software base and existing images; this trusted adapter is
mounted with each release, alongside the environment preparation recipe.
"""
from pathlib import Path


def executable(path):
    with path.open('rb') as source:magic=source.read(4)
    return magic.startswith((b'\x7fELF',b'#!',b'MZ')) or magic in (b'\xfe\xed\xfa\xce',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xcf\xfa\xed\xfe')


def select_binary(destination,name,relative=None):
    destination=Path(destination);root=destination.resolve()
    if Path(name).name!=name or name in ('','.','..'):raise ValueError('Nome eseguibile non valido')
    if relative is not None:
        matches=[destination/relative]
    else:
        excluded={'bash-completion','completions','fish','zsh','man','doc','docs'}
        matches=[p for p in destination.rglob(name) if p.is_file() and p.resolve().is_relative_to(root)
                 and not excluded.intersection(p.relative_to(destination).parts[:-1]) and executable(p)]
        canonical=[p for p in matches if p.parent.name=='bin']
        if len(canonical)==1:matches=canonical
    if len(matches)!=1 or not matches[0].is_file() or not matches[0].resolve().is_relative_to(root):
        raise RuntimeError(f'Atteso un eseguibile interno {name}, trovati {matches}')
    return matches[0].resolve()


def install_binaries(app,destination,bin_dir):
    main=app.get('binary',app['executable']);binary=None
    for name,relative in app.get('binary_paths',{main:None}).items():
        target=select_binary(destination,name,relative)
        target.chmod(target.stat().st_mode|0o111)
        link=Path(bin_dir)/name
        if link.exists() or link.is_symlink():raise RuntimeError(f'Non sovrascrivo un eseguibile esistente: {link}')
        link.symlink_to(target)
        if name==main:binary=target
    if binary is None:raise ValueError('Eseguibile principale mancante dai percorsi dichiarati')
    return binary


def main():
    import install_righaven
    install_righaven.install_binaries=install_binaries
    install_righaven.main()


if __name__=='__main__':main()
