# Lab Icons Windows

Gerenciador local para importar icones PNG, gerar ICOs compativeis com Windows e aplicar customizacoes em atalhos e pastas com uma interface visual simples.

O projeto prioriza seguranca: ele nao modifica executaveis, DLLs, arquivos do sistema ou registro do Windows. As alteracoes sao feitas em atalhos `.lnk` selecionados pelo usuario e em pastas escolhidas pelo usuario usando `desktop.ini`.

## Features e Como Funciona

### Biblioteca visual

- Os PNGs de entrada ficam em `icons-in/`.
- A biblioteca atualiza automaticamente quando novos PNGs sao adicionados.
- Os PNGs mais recentes aparecem primeiro.
- A lista da direita mostra miniaturas limpas, sem fundo branco quando detectado.
- Ao selecionar um PNG, o app prepara apenas aquele icone em segundo plano.
- O botao **Processar pacote em background** continua existindo para preparar todos os PNGs sem travar a tela.
- O botao **Abrir pasta icons-out** abre os icones gerados no Explorer.

### Geracao de icones

- Remove fundo branco conectado as bordas quando detectado.
- Suaviza marcas visuais simples nos cantos.
- Gera ICOs grandes e compativeis com Windows: 16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128 e 256 px.
- Mantem tambem um PNG limpo em `icons-out/png/` em 1024 px para preview e usos futuros.

### Aplicacao em apps e pastas

- Atalhos usam alteracao segura do proprio `.lnk`.
- Pastas usam `desktop.ini`, mecanismo padrao do Windows para icones de pasta.
- O app preserva metadados de pastas especiais, como Music, Documents e Pictures.
- Ao aplicar icone em pasta, o ICO e copiado para `.lab-icons-windows/` dentro da propria pasta.
- O arquivo aplicado recebe hash no nome para evitar que o Explorer reutilize cache antigo de icone.
- O app le `desktop.ini` em UTF-16/UTF-8, entende `IconFile`, `IconResource`, caminhos relativos e indice do icone.
- O painel central mostra original e atual/customizado.
- **Salvar e aplicar** grava o mapeamento e aplica o icone em uma unica acao.

### Destinos detectados

O app lista:

- Atalhos do Menu Iniciar.
- Atalhos da Area de Trabalho.
- Apps modernos do Windows via `Get-StartApps`, como WhatsApp e Spotify.
- Pastas comuns do usuario, como Desktop, Documents, Downloads, Music, Pictures, Videos e Workspace.

Os itens sao agrupados por temas como Browsers, Dev, Editores, Office, Design, Media, Games, Comunicacao, Seguranca, VPN, Sistema Windows, Pastas do usuario, Trabalho e Pessoal.

Apps modernos do Windows nem sempre expoem um `.lnk` editavel. Para esses casos, o app cria um atalho gerenciado em `config/managed-shortcuts/` apontando para `shell:AppsFolder\...` e aplica o icone nesse atalho.

### Reaplicacao automatica

A opcao global cria um atalho na pasta Startup do usuario. Ao iniciar o Windows, o app roda em modo de reaplicacao unica e reaplica icones customizados que tenham sido trocados por atualizacoes de apps ou alteracoes do Windows.

### Aparencia e desempenho

- A janela usa CustomTkinter e ajustes DWM do Windows para dark mode, cantos arredondados e backdrop nativo quando disponivel.
- A descoberta de apps roda em segundo plano.
- A lista de apps detectados so e renderizada quando a aba **Detectados** e aberta.
- O arquivo `config/mappings.json` evita reler o JSON inteiro em salvamentos sem mudanca; no caminho comum ele compara o estado serializado em memoria com a ultima gravacao e ainda preserva troca atomica quando precisa escrever.
- O carregamento de `mappings.json` aceita UTF-8, UTF-8 com BOM e UTF-16 para tolerar arquivos salvos por ferramentas do Windows.
- Arquivos locais de mapeamento vazios ou contendo apenas comentarios sao tratados como configuracao inicial, o que permite usar placeholders redigidos sem impedir a abertura do app.
- A atualizacao da biblioteca em `icons-in/` reaproveita a mesma varredura para ordenar PNGs e detectar mudancas, reduzindo IO durante startup e refreshes da galeria.
- Quando `icons-in/` ja contem PNGs, a tela pula a varredura recursiva de `icons-out/ico/`; o fallback para ICOs so roda quando a biblioteca de origem esta vazia.
- A galeria precomputa grupo, caminho relativo e estado pronto/novo de cada item durante `refresh_icons()`, evitando repetir essas derivacoes e `stat()` a cada rerender e durante a digitacao no filtro.
- A geracao de cada icone reutiliza a mesma base quadrada para PNG e ICO, cortando uma etapa de preparo por arquivo e reduzindo CPU em lotes maiores.
- A descoberta de atalhos e pastas evita `Path.resolve()` ao montar chaves internas, usando caminho absoluto normalizado do Windows para reduzir IO extra durante startup e na criacao manual de mapeamentos.
- A aplicacao de icones em atalhos e pastas agora calcula o nome versionado do ICO com hash em streaming, evitando carregar o arquivo inteiro na memoria a cada reaplicacao.
- Previews extraidos de `.lnk`, `.exe` e outros arquivos do Windows passam a invalidar o cache automaticamente quando o arquivo de origem muda, evitando miniaturas antigas apos updates de apps ou troca de icone.
- A extracao de previews nativos do Windows libera `HICON` e `DC` logo apos o uso, evitando acumulo de handles em refreshes repetidos da lista e da galeria.
- O cache em memoria das miniaturas da UI agora e limitado e substitui entradas antigas do mesmo arquivo quando o preview muda, evitando crescimento continuo de RAM em sessoes longas com muitas atualizacoes de icones.
- Logs de performance sao gravados em `config/performance.log`.
- O comando `python app.py --perf-smoke` mede o carregamento da janela sem abrir o app para uso normal.

## Estrutura

```text
lab-icons-windows/
  app.py
  requirements.txt
  icons-in/
  icons-out/
    ico/
    png/
  config/
    mappings.json
    performance.log
    managed-shortcuts/
    icon-cache/
  src/
  tests/
```

## Requisitos

- Windows 10 ou 11
- Python 3.10+

## Instalacao

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Como Usar

1. Coloque PNGs em `icons-in/`.
2. Inicie o app:

```powershell
python app.py
```

3. Selecione um PNG na biblioteca visual.
4. Selecione um destino na aba **Detectados**, ou use **Adicionar App** / **Adicionar Pasta**.
5. Confira os previews de original e atual/customizado.
6. Clique em **Salvar e aplicar**.
7. Ative **Reaplicar no boot** se quiser reaplicacao automatica ao iniciar o Windows.

## Configuracao Salva

Os mapeamentos ficam em `config/mappings.json`.

```json
{
  "version": 1,
  "settings": {
    "auto_check_seconds": 60,
    "global_auto_reapply": true,
    "startup_reapply_enabled": true
  },
  "mappings": [
    {
      "id": "notepad",
      "program_name": "Notepad",
      "program_group": "Sistema Windows",
      "shortcut_path": "C:\\Users\\you\\Desktop\\Notepad.lnk",
      "target_type": "shortcut",
      "icon_group": "editors",
      "source_icon": "icons-in\\editors\\notepad.png",
      "ico_path": "icons-out\\ico\\editors\\notepad.ico",
      "png_path": "icons-out\\png\\editors\\notepad.png",
      "preferred_asset": "ico",
      "original_icon": "C:\\Windows\\System32\\notepad.exe,0",
      "is_customized": true,
      "known_key": "shortcut:C:\\Users\\you\\Desktop\\Notepad.lnk",
      "auto_reapply": false
    }
  ]
}
```

## Seguranca

O app:

- Trabalha em pastas locais do projeto ou na pasta do executavel.
- Altera apenas atalhos `.lnk` e pastas escolhidas pelo usuario.
- Nao roda como administrador.
- Nao instala servico em background.
- Nao altera o registro do Windows para trocar icones de apps.
- Preserva e faz backup do `desktop.ini` quando customiza pastas.

Alteracoes de `DefaultIcon` no registro sao adequadas para associacoes de arquivos ou instaladores. Para este app, a rota segura e `.lnk` para atalhos e `desktop.ini` para pastas.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall app.py src
.\.venv\Scripts\python.exe app.py --perf-smoke
```

Os testes cobrem pipeline de imagem, persistencia de customizados, classificacao de apps, preservacao/leitura de `desktop.ini` e desempenho da descoberta.

## Build Windows

Para usar como aplicativo Windows sem console:

```powershell
.\scripts\build_windows.ps1
```

O build sai em `dist/Lab Icons Windows/`. Em modo executavel, `icons-in/`, `icons-out/` e `config/` ficam ao lado do `.exe`, facilitando manutencao.

Para gerar um unico `.exe`:

```powershell
.\scripts\build_windows.ps1 -OneFile
```

## Proximas Etapas

- Teste visual automatizado da interface com screenshots para detectar quebras de layout.
- Watcher de filesystem nativo para `icons-in/` em vez de polling simples.
- Cache persistente dos apps detectados para abrir a tela ainda mais rapido.
- Filtro por grupo e tipo na biblioteca de icones.
- Editor manual de temas e aliases de apps conhecidos.
- Melhor correspondencia em **Carregar grupo de icones**, com fuzzy matching e confirmacao antes de aplicar.
- Exportar/importar pacotes de temas.
- Opcao avancada para limpar cache de icones do Explorer quando o Windows demorar a refletir mudancas.
- Avaliar migracao futura para WinUI 3 se o projeto precisar de integracao visual totalmente nativa.
