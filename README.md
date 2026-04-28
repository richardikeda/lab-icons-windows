# Lab Icons Windows

Gerenciador local para importar icones PNG, gerar ICOs compativeis com Windows e aplicar customizacoes em atalhos e pastas com uma interface visual simples.

O projeto prioriza seguranca: ele nao modifica executaveis, DLLs, arquivos `.mun`, arquivos do sistema ou registro do Windows. As alteracoes sao feitas em atalhos `.lnk` selecionados pelo usuario e em pastas escolhidas pelo usuario usando `desktop.ini`, preservando os binarios originais e evitando quebra de assinaturas digitais.

## Features e Como Funciona

### Biblioteca visual

- Em desenvolvimento, os PNGs de entrada ficam em `icons-in/` no repo. Em build/execucao instalada, ficam em `%LOCALAPPDATA%\LabIcons\icons-in\`.
- A biblioteca atualiza automaticamente quando novos PNGs sao adicionados.
- Os PNGs mais recentes aparecem primeiro.
- A lista da direita mostra miniaturas limpas, sem fundo branco quando detectado.
- Ao selecionar um PNG, o app prepara apenas aquele icone em segundo plano.
- O botao **Processar pacote em background** continua existindo para preparar todos os PNGs sem travar a tela.
- O botao **Abrir pasta icons-out** abre a pasta de icones gerados do ambiente atual no Explorer.
- O botao **Importar tema** aceita ZIP ou pasta com PNGs e manifesto JSON e abre uma tela de revisao antes de aplicar.
- O botao **Excluir tema** remove os PNGs importados daquele tema e os mapeamentos associados.

### Geracao de icones

- Remove fundo branco conectado as bordas quando detectado.
- Suaviza marcas visuais simples nos cantos.
- Gera ICOs grandes e compativeis com Windows: 16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128 e 256 px.
- Mantem canal alfa RGBA para transparencia graduada, bordas suavizadas e sombras.
- Inclui tamanhos pequenos dedicados em vez de depender apenas do redimensionamento automatico de 256 px para 16/24/32 px.
- Mantem tambem um PNG limpo em `icons-out/png/` em 1024 px para preview e usos futuros.

### Aplicacao em apps e pastas

- Atalhos usam alteracao segura do proprio `.lnk` via COM/`IShellLink`, sem editar o aplicativo de destino.
- Pastas usam `desktop.ini`, mecanismo padrao do Windows para icones de pasta.
- O app preserva metadados de pastas especiais, como Music, Documents e Pictures.
- Ao aplicar icone em pasta, o ICO e copiado para `.lab-icons-windows/` dentro da propria pasta.
- O arquivo aplicado recebe hash no nome para evitar que o Explorer reutilize cache antigo de icone.
- O app le `desktop.ini` em UTF-16/UTF-8, entende `IconFile`, `IconResource`, caminhos relativos e indice do icone.
- A pasta recebe atributos `System` e `Read-only`, requisito do Shell para processar `desktop.ini`.
- O `desktop.ini` aplicado usa `IconResource=...,0` e tambem grava `IconFile`/`IconIndex` para compatibilidade.
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

O app nao altera manifestos `AppxManifest.xml` de apps UWP/Store instalados. Essa escolha segue a rota menos invasiva: criar um atalho secundario editavel e alterar o icone desse atalho.

### Temas prontos

Um tema pode ser uma pasta ou um `.zip` contendo PNGs e um manifesto `theme.json`, `config.json` ou `manifest.json`.

Exemplo:

```json
{
  "theme": "Meu Tema",
  "icons": [
    {
      "file": "assets/spotify.png",
      "program": "Spotify",
      "group": "media",
      "program_group": "Comunicacao",
      "target_type": "shortcut"
    }
  ]
}
```

Campos suportados:

- `theme` ou `name`: nome do tema.
- `icons[].file` ou `icons[].png`: caminho relativo do PNG dentro do pacote.
- `icons[].program`, `program_name` ou `app`: nome usado para associar o icone a apps detectados.
- `icons[].group`: grupo visual dentro da biblioteca.
- `icons[].program_group` ou `category`: grupo exibido na lista de customizados.
- `icons[].target_type` ou `kind`: `shortcut` ou `folder`.
- `icons[].target_path` ou `path`: caminho explicito do alvo, quando o nome nao for suficiente.

Na importacao, os PNGs sao copiados para `icons-in/themes/<Tema>/...` dentro da pasta de dados do ambiente atual e aparecem em uma janela **Tema: <nome>**. A janela separa itens encontrados, sugestoes fuzzy que exigem confirmacao, itens nao encontrados e erros. O usuario pode confirmar sugestoes, associar manualmente um destino detectado, ignorar itens e aplicar apenas os itens confirmados. Associacoes manuais ficam em `.lab-icons-theme-associations.json` dentro da pasta importada do tema; o ZIP original nunca e alterado.

### Reaplicacao automatica

A opcao global cria um atalho na pasta Startup do usuario. Ao iniciar o Windows, o app roda em modo de reaplicacao unica e reaplica icones customizados que tenham sido trocados por atualizacoes de apps ou alteracoes do Windows.

Por padrao, novas customizacoes ficam com reaplicacao ligada. O arquivo `config/mappings.json` guarda o icone original, o icone aplicado, o PNG de origem, o tipo do alvo, o tema associado quando existir e os dados de boot. A interface tambem tem **Ver config** para visualizar esse arquivo sem sair do app.

### Restauracao global

O botao **Restaurar todos para o padrao** restaura o estado visual de todas as customizacoes ativas sem apagar mapeamentos, temas, icones importados ou backups. Antes de executar, ele mostra a contagem de atalhos, pastas, itens de tema e itens com/sem backup. Cada item e restaurado individualmente: atalhos usam `original_icon` e caem para `backup_icon_path` quando o original nao esta disponivel; pastas usam `backup_desktop_ini_path` quando existe e depois o fallback seguro de `desktop.ini` gerenciado. Sucessos ficam com `is_customized=false`; falhas permanecem customizadas para nova tentativa.

### Aparencia e desempenho

- A janela usa CustomTkinter e ajustes DWM do Windows para dark mode, cantos arredondados e backdrop nativo quando disponivel.
- A descoberta de apps roda em segundo plano.
- A lista de apps detectados so e renderizada quando a aba **Detectados** e aberta.
- O arquivo `config/mappings.json` evita reler o JSON inteiro em salvamentos sem mudanca; no caminho comum ele compara o estado serializado em memoria com a ultima gravacao e ainda preserva troca atomica quando precisa escrever.
- O carregamento de `mappings.json` aceita UTF-8, UTF-8 com BOM e UTF-16 para tolerar arquivos salvos por ferramentas do Windows.
- A importacao de temas valida caminhos relativos, rejeita ZIP com traversal, limita volume/quantidade de arquivos e copia apenas PNGs declarados no manifesto.
- Arquivos locais de mapeamento vazios ou contendo apenas comentarios sao tratados como configuracao inicial, o que permite usar placeholders redigidos sem impedir a abertura do app.
- A atualizacao da biblioteca em `icons-in/` reaproveita a mesma varredura para ordenar PNGs e detectar mudancas, reduzindo IO durante startup e refreshes da galeria.
- Quando `icons-in/` ja contem PNGs, a tela pula a varredura recursiva de `icons-out/ico/`; o fallback para ICOs so roda quando a biblioteca de origem esta vazia.
- A galeria precomputa grupo, caminho relativo e estado pronto/novo de cada item durante `refresh_icons()`, evitando repetir essas derivacoes e `stat()` a cada rerender e durante a digitacao no filtro.
- A geracao de cada icone reutiliza a mesma base quadrada para PNG e ICO, cortando uma etapa de preparo por arquivo e reduzindo CPU em lotes maiores.
- O processamento em lote agora pula PNGs cujos `.ico` e previews limpos ja estao atualizados, evitando reencodar toda a biblioteca quando nada mudou.
- A descoberta de atalhos e pastas evita `Path.resolve()` ao montar chaves internas, usando caminho absoluto normalizado do Windows para reduzir IO extra durante startup e na criacao manual de mapeamentos.
- A descoberta inicial agora executa em paralelo a leitura das pastas comuns, a varredura de atalhos `.lnk` e o `Get-StartApps`, reduzindo o tempo total de startup quando o Menu Iniciar/Desktop tem muitos itens.
- A aplicacao de icones em atalhos e pastas agora calcula o nome versionado do ICO com hash em streaming, evitando carregar o arquivo inteiro na memoria a cada reaplicacao.
- Previews extraidos de `.lnk`, `.exe` e outros arquivos do Windows passam a invalidar o cache automaticamente quando o arquivo de origem muda, evitando miniaturas antigas apos updates de apps ou troca de icone.
- A extracao de previews nativos tenta `PrivateExtractIconsW` em 256 px primeiro, o que melhora fidelidade para bibliotecas modernas, executaveis, DLLs e arquivos `.mun` lidos como PE quando o Windows permite; se falhar, usa `ExtractIconEx` e depois `SHGetFileInfo`.
- A extracao libera `HICON` e `DC` logo apos o uso, evitando acumulo de handles em refreshes repetidos da lista e da galeria.
- O cache em memoria das miniaturas da UI agora e limitado e substitui entradas antigas do mesmo arquivo quando o preview muda, evitando crescimento continuo de RAM em sessoes longas com muitas atualizacoes de icones.
- Logs de performance sao gravados em `config/performance.log` na pasta de dados do ambiente atual; relatorios de rollback sao gravados em `%LOCALAPPDATA%\LabIcons\Logs\rollback-report-YYYYMMDD-HHMMSS.json`.
- Backups reais dos icones originais ficam em `%LOCALAPPDATA%\LabIcons\Backups\`, usando nomes estaveis com hash do alvo/recurso e timestamp quando necessario.
- O comando `python app.py --perf-smoke` mede o carregamento da janela sem abrir o app para uso normal.

## Conformidade com Iconografia do Windows

Este projeto implementa apenas os mecanismos seguros para customizacao por usuario:

- **ICO multiescala:** os arquivos gerados incluem representacoes de 16 a 256 px, com alfa RGBA para transparencia moderna.
- **Pastas:** usa `desktop.ini` em UTF-16, grava `IconResource`, preserva metadados existentes, faz backup do arquivo original e aplica atributos exigidos pelo Explorer.
- **Atalhos:** usa a interface COM de atalhos do Windows para `SetIconLocation`, mantendo o alvo original intacto.
- **Apps UWP/Store:** usa atalhos gerenciados para `shell:AppsFolder\AppID`, sem editar manifesto AppX nem assets instalados pelo pacote.
- **Atualizacao do Shell:** usa `SHChangeNotify` com eventos especificos de item/pasta para reduzir impacto no Explorer.
- **Reversibilidade:** guarda o icone original no mapeamento e mantem copias versionadas por hash para evitar cache antigo.
- **Temas:** importa assets para a biblioteca local do usuario/projeto, sem executar scripts ou alterar arquivos fora de `icons-in/themes`.

Fora de escopo por seguranca:

- Editar recursos internos de `.exe`, `.dll` ou `.mun`.
- Alterar `HKLM`, `HKCU\Software\Classes`, `DefaultIcon`, CLSIDs do sistema ou associacoes globais de arquivo.
- Substituir assets de aplicativos UWP instalados.
- Limpar agressivamente `IconCache.db` ou reiniciar `explorer.exe` automaticamente.

Essas operacoes continuam tecnicamente possiveis no Windows, mas exigem privilegios, afetam todo o sistema ou podem quebrar assinaturas digitais. Para este app, a abordagem correta e preferir `.lnk` e `desktop.ini`.

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
  Backups/
  Logs/
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
7. Mantenha **Reaplicar no boot** ativo para reaplicacao automatica ao iniciar o Windows.
8. Use **Ver config** para inspecionar o `mappings.json`.
9. Use **Importar tema** para carregar ZIPs ou pastas com manifesto.

## Configuracao Salva

Em desenvolvimento, os mapeamentos ficam em `config/mappings.json`. Em build/execucao instalada, ficam em `%LOCALAPPDATA%\LabIcons\config\mappings.json`.

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
      "backup_icon_path": "C:\\Users\\you\\AppData\\Local\\LabIcons\\Backups\\hash-20260427T200000Z.ico",
      "backup_desktop_ini_path": "",
      "backup_created_at": "2026-04-27T20:00:00Z",
      "is_customized": true,
      "known_key": "shortcut:C:\\Users\\you\\Desktop\\Notepad.lnk",
      "auto_reapply": true,
      "theme_name": "Meu Tema"
    }
  ]
}
```

## Seguranca

O app:

- Em desenvolvimento, trabalha nas pastas locais do projeto.
- Em build/execucao instalada, grava configuracoes, logs, cache, atalhos gerenciados, `icons-in/` e `icons-out/` em `%LOCALAPPDATA%\LabIcons\`.
- Grava backups reais em `%LOCALAPPDATA%\LabIcons\Backups\` e relatorios de rollback em `%LOCALAPPDATA%\LabIcons\Logs\`.
- Altera apenas atalhos `.lnk` e pastas escolhidas pelo usuario.
- Nao roda como administrador.
- Nao instala servico em background.
- Nao altera o registro do Windows para trocar icones de apps.
- Nao edita EXE, DLL, MUN ou manifestos AppX.
- Preserva e faz backup do `desktop.ini` quando customiza pastas.
- Importa temas sem executar conteudo do pacote; somente PNGs declarados no manifesto sao copiados.
- Restaura customizacoes globais sem apagar mapeamentos, preservando metadados de tema e associacoes manuais.

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

O build sai em `dist/Lab Icons Windows/`. Em modo executavel/congelado, dados mutaveis ficam em `%LOCALAPPDATA%\LabIcons\` para evitar escrita na pasta de instalacao.

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
- Busca/filtro dentro da janela de associacao manual de temas.
- Exportar pacote de tema a partir dos icones/mapeamentos atuais.
- Opcao avancada para limpar cache de icones do Explorer quando o Windows demorar a refletir mudancas.
- Avaliar migracao futura para WinUI 3 se o projeto precisar de integracao visual totalmente nativa.
