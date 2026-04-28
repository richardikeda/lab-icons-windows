# Documento Tecnico - Lab Icons Windows

## 1. Objetivo

O Lab Icons Windows e um gerenciador local de iconografia para Windows. Ele importa imagens PNG, gera arquivos ICO multiescala compativeis com o Shell do Windows e aplica esses icones em atalhos `.lnk` e pastas selecionadas pelo usuario.

O projeto foi desenhado para personalizacao segura por usuario. A regra central e preservar os binarios originais do sistema e dos aplicativos. Por isso, o programa altera apenas artefatos de personalizacao suportados pelo Windows: atalhos, arquivos `desktop.ini` em pastas escolhidas e arquivos de configuracao locais do proprio app.

## 2. Escopo Funcional

O programa deve:

- Ler PNGs em `icons-in/` na pasta de dados do ambiente atual.
- Gerar ICOs em `icons-out/ico/` na pasta de dados do ambiente atual.
- Gerar PNGs limpos em `icons-out/png/` para preview e usos futuros.
- Detectar atalhos do Menu Iniciar, Area de Trabalho e pastas comuns do usuario.
- Detectar apps modernos via `Get-StartApps` e criar atalhos gerenciados quando necessario.
- Aplicar icones em atalhos usando COM/`IShellLink`.
- Aplicar icones em pastas usando `desktop.ini`.
- Guardar mapeamentos, icones originais e estado de reaplicacao em `config/mappings.json`.
- Reaplicar customizacoes no boot quando apps, atalhos ou pastas forem modificados.
- Permitir visualizar o arquivo de configuracao pela interface.
- Importar temas prontos por pasta ou ZIP com manifesto JSON.
- Excluir temas importados e remover seus mapeamentos.

O programa deve operar sem privilegios administrativos e sem modificar o Registro para trocar icones de aplicativos.

## 3. Estrutura do Projeto

```text
lab-icons-windows/
  app.py
  README.md
  docs/
    TECHNICAL.md
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
    app_paths.py
    app_discovery.py
    appx_manager.py
    file_hashing.py
    folder_manager.py
    icon_pipeline.py
    icon_preview.py
    mapping_store.py
    perf_logger.py
    rollback_report.py
    reapply_service.py
    shell_notify.py
    shortcut_manager.py
    startup_manager.py
    theme_manager.py
    ui.py
    windows_native.py
  tests/
```

## 4. Componentes

### `app.py`

E o ponto de entrada. Ele cria as pastas essenciais, inicia a interface normal ou executa modos especiais:

- `--reapply-once`: carrega `config/mappings.json` e reaplica icones alterados.
- `--perf-smoke`: abre a janela, mede tempo de inicializacao e fecha.

Os caminhos mutaveis sao resolvidos por `src/app_paths.py`: em desenvolvimento, o app usa `config/`, `icons-in/` e `icons-out/` no repo; em execucao congelada/instalada, usa `%LOCALAPPDATA%\LabIcons\` para configuracao, logs, cache, atalhos gerenciados e assets gerados/importados.

### `src/app_paths.py`

Centraliza os caminhos do app. O modulo diferencia execucao via `python app.py` de execucao congelada (`sys.frozen`) e evita gravar dados mutaveis ao lado do executavel instalado. Para compatibilidade, ao iniciar em modo congelado ele reaproveita uma copia existente de `config/`, `icons-in/` ou `icons-out/` ao lado do executavel apenas se a pasta correspondente ainda nao existir em `%LOCALAPPDATA%\LabIcons\`.

### `src/ui.py`

Contem a interface CustomTkinter e orquestra os fluxos de usuario:

- selecao de destino;
- selecao de icone;
- processamento individual ou em lote;
- visualizacao de previews;
- salvamento e aplicacao;
- reaplicacao manual;
- visualizacao de `mappings.json`;
- importacao e exclusao de temas.
- revisao de temas antes de aplicar;
- restauracao global com relatorio estruturado.

A UI evita renderizar listas pesadas antes da hora. A lista de apps detectados so e desenhada quando a aba `Detectados` e aberta, e filtros usam indice textual precomputado.

### `src/icon_pipeline.py`

Processa PNGs de entrada. O pipeline:

1. Abre o PNG em RGBA.
2. Remove fundo branco conectado as bordas quando detectado.
3. Suaviza marcas visuais simples nos cantos.
4. Centraliza a imagem em canvas quadrado transparente.
5. Salva PNG limpo em 1024 px.
6. Salva ICO multiescala.

Os tamanhos gerados sao:

```text
16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256
```

Essa estrategia evita depender apenas do redimensionamento automatico do Windows, melhorando nitidez em tamanhos pequenos e telas HiDPI.

### `src/shortcut_manager.py`

Altera atalhos `.lnk` usando COM. O fluxo esperado e:

1. Criar um objeto `ShellLink`.
2. Carregar o `.lnk` com `IPersistFile`.
3. Chamar `SetIconLocation(caminho, indice)`.
4. Salvar o `.lnk`.
5. Notificar o Shell.

Antes de aplicar, o app cria uma copia versionada do ICO em `.applied/`, com hash no nome. Isso ajuda a evitar que o Explorer reaproveite cache antigo quando o usuario troca o conteudo visual de um icone.

### `src/folder_manager.py`

Aplica icones de pasta pelo mecanismo padrao do Windows: `desktop.ini`.

O app:

- copia o ICO para `.lab-icons-windows/` dentro da pasta alvo;
- gera nome versionado por hash;
- preserva `desktop.ini` existente em backup;
- escreve `IconResource=...,0`;
- tambem grava `IconFile` e `IconIndex` por compatibilidade;
- grava `desktop.ini` em UTF-16;
- marca `desktop.ini` como oculto e sistema;
- marca a pasta como sistema e somente leitura;
- notifica o Shell.

Esse comportamento e necessario porque o Explorer so processa `desktop.ini` para pastas com atributos adequados.

### `src/reapply_service.py`

Decide se um icone precisa ser reaplicado. Para cada mapeamento customizado:

- verifica se a customizacao ainda esta presente;
- reaplica se o atalho ou a pasta voltou ao icone antigo;
- captura icone original antes da primeira aplicacao;
- restaura icone original quando solicitado.

Para rollback global, a UI chama `src.rollback_report.restore_all_to_default()`, que restaura item por item via `restore_mapping`, marca sucesso com `is_customized=false`, mantem falhas como customizadas e preserva todos os metadados do mapping.

No boot, `app.py --reapply-once` usa esse servico para recuperar customizacoes perdidas por atualizacoes de aplicativos ou alteracoes do Windows.

### `src/mapping_store.py`

Gerencia `config/mappings.json` dentro da pasta de dados do ambiente atual.

O arquivo guarda:

- nome do programa ou pasta;
- grupo visual;
- caminho do atalho ou pasta;
- tipo do alvo;
- caminho do PNG de origem;
- caminho do ICO aplicado;
- caminho do PNG limpo;
- icone original;
- caminhos de backup real (`backup_icon_path`, `backup_desktop_ini_path`, `backup_created_at`);
- estado `is_customized`;
- estado `auto_reapply`;
- chave conhecida de descoberta;
- nome do tema, quando importado;
- configuracoes globais.

O salvamento e atomico: o conteudo e escrito em arquivo temporario e depois movido para o destino com `os.replace`. O store evita regravar o arquivo quando nao ha mudanca real.

### `src/theme_manager.py`

Importa temas por ZIP ou pasta.

Um tema deve conter um manifesto chamado `theme.json`, `config.json` ou `manifest.json`. O formato recomendado e:

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

Na importacao:

- caminhos absolutos sao rejeitados;
- `..` e traversal em ZIP sao rejeitados;
- existe limite de quantidade e tamanho total;
- somente PNGs declarados no manifesto sao copiados;
- os arquivos vao para `icons-in/themes/<Tema>/...`;
- os PNGs copiados sao enviados para uma tela de revisao antes de aplicar;
- associacoes exatas ficam confirmadas, sugestoes fuzzy exigem confirmacao e itens nao encontrados podem receber associacao manual;

Associacoes manuais sao persistidas em `.lab-icons-theme-associations.json` dentro da pasta do tema importado, sem alterar ZIPs ou pastas originais.

Na exclusao de tema, o app remove a pasta do tema e os mapeamentos associados. Se algum item estava customizado, tenta restaurar antes de remover o mapeamento.

### `src/icon_preview.py`

Gera previews de icones atuais e originais.

Para arquivos `.png` e `.ico`, usa o proprio arquivo. Para binarios e atalhos, tenta extracao nativa:

1. `PrivateExtractIconsW` em 256 px.
2. Fallback para `ExtractIconEx`.
3. Fallback para `SHGetFileInfo`.

Handles nativos (`HICON`, DCs) sao liberados imediatamente apos o uso. O cache de previews inclui mtime e tamanho do arquivo de origem para invalidar miniaturas antigas apos updates.

### `src/app_discovery.py`

Descobre destinos provaveis:

- atalhos no Menu Iniciar;
- atalhos na Area de Trabalho;
- atalhos publicos;
- apps modernos via PowerShell;
- pastas comuns do usuario.

Cada item recebe uma chave normalizada para evitar duplicatas e permitir que mapeamentos sejam reencontrados em sessoes futuras.

### `src/appx_manager.py`

Cria atalhos gerenciados para apps UWP/Store quando o app nao dispoe de `.lnk` editavel. O destino aponta para:

```text
explorer.exe shell:AppsFolder\<AppID>
```

O icone e aplicado nesse atalho gerenciado, nao no pacote AppX.

### `src/startup_manager.py`

Cria ou remove um atalho na pasta Startup do usuario:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

O atalho executa:

```text
python app.py --reapply-once
```

Em build congelado, usa o executavel atual como runtime para executar `--reapply-once`.

### `src/shell_notify.py`

Envia notificacoes ao Shell com `SHChangeNotify`.

O app usa eventos especificos para item ou pasta, evitando operacoes globais agressivas sempre que possivel.

### `src/perf_logger.py`

Registra metricas em `config/performance.log` na pasta de dados do ambiente atual, em formato JSON Lines. O objetivo e medir rotas de inicializacao, descoberta, renderizacao e processamento sem adicionar dependencias pesadas.

### `src/rollback_report.py`

Calcula contagens de rollback, executa restauracao global e grava relatorios JSON em `%LOCALAPPDATA%\LabIcons\Logs\`. O relatorio contem timestamp, totais, itens restaurados, itens com erro, alvo, tipo, tema, caminhos de backup e mensagem de erro. O fluxo nao remove temas, arquivos de tema nem mapeamentos.

## 5. Fluxo de Uso Esperado

### Fluxo manual

1. Usuario coloca PNGs em `icons-in/`.
2. App detecta a biblioteca.
3. Usuario seleciona um PNG.
4. App gera ICO e PNG limpo se ainda nao estiverem prontos.
5. Usuario seleciona app, atalho ou pasta.
6. App captura o icone original.
7. App salva o mapeamento.
8. App aplica o icone.
9. App notifica o Shell.
10. App marca o mapeamento como customizado e reaplicavel.

### Fluxo de reaplicacao

1. Windows inicia.
2. Atalho de Startup chama `--reapply-once`.
3. App carrega `mappings.json`.
4. Para cada mapeamento customizado, verifica se o icone ainda esta aplicado.
5. Se nao estiver, reaplica.
6. O processo encerra sem abrir a interface.

### Fluxo de tema

1. Usuario escolhe ZIP ou pasta.
2. App extrai ou copia para area temporaria.
3. App valida manifesto.
4. App copia PNGs declarados para `icons-in/themes/<Tema>/`.
5. App atualiza a biblioteca visual.
6. App abre a tela de revisao do tema.
7. Usuario confirma sugestoes fuzzy ou associa itens manualmente.
8. App cria e aplica mapeamentos reaplicaveis apenas para itens confirmados.

### Fluxo de rollback global

1. Usuario aciona **Restaurar todos para o padrao**.
2. App calcula contagens de customizacoes, atalhos, pastas, itens de tema e disponibilidade de backup.
3. Usuario confirma a operacao.
4. App tenta restaurar cada mapping customizado via `restore_mapping`.
5. Sucessos ficam com `is_customized=false`; falhas permanecem `is_customized=true`.
6. App salva `rollback-report-YYYYMMDD-HHMMSS.json` em `%LOCALAPPDATA%\LabIcons\Logs\`.

## 6. Como Deve Funcionar

O comportamento correto esperado e:

- Qualquer customizacao aplicada deve ficar registrada em `mappings.json`.
- O icone original deve ser capturado antes da primeira aplicacao sempre que o Windows permitir.
- Backups reais devem ser mantidos em `%LOCALAPPDATA%\LabIcons\Backups\` e usados como fallback de restauracao.
- Customizacoes devem ser reaplicadas no boot se o usuario mantiver a opcao ativa.
- A interface deve continuar responsiva durante processamento em lote.
- A importacao de temas deve ser segura mesmo para ZIPs externos.
- O app deve preferir caminhos locais versionados por hash para reduzir problemas de cache.
- O app deve preservar metadados existentes de `desktop.ini`, removendo apenas chaves de icone que ele precisa substituir.
- O app deve falhar de forma visivel e reversivel quando nao conseguir alterar um item.

## 7. O Que E Esperado Pelo Usuario

O usuario pode esperar:

- Uma biblioteca de icones agrupada por pastas e temas.
- Previews de icone original e icone novo.
- Persistencia das escolhas entre sessoes.
- Reaplicacao automatica quando atualizacoes de apps removerem customizacoes.
- Restauracao de atalhos e pastas customizados pelo app.
- Restauracao global com relatorio auditavel sem perder mapeamentos ou temas.
- Importacao de temas sem risco de execucao de scripts.
- Operacao sem permissao de administrador.

O usuario nao deve esperar que a troca apareca sempre instantaneamente em todos os locais do Explorer. O Shell do Windows possui cache proprio; o app notifica mudancas, mas alguns cenarios podem demorar ate o Explorer atualizar.

## 8. Segurança

O modelo de seguranca do projeto e conservador:

- nao edita binarios;
- nao altera recursos internos;
- nao usa elevacao administrativa;
- nao modifica associacoes globais;
- nao executa conteudo importado;
- valida caminhos de ZIP e manifesto;
- limita importacao de tema;
- preserva backups de `desktop.ini`;
- preserva backups reais de icones originais;
- usa copias versionadas dos ICOs aplicados.

Essa abordagem reduz risco de quebrar assinaturas digitais, gerar falsos positivos de antivirus ou afetar outros usuarios da maquina.

## 9. Performance

Principios de performance:

- varrer `icons-in/` uma vez e reutilizar snapshot;
- evitar fallback para varredura de `icons-out/ico/` quando PNGs de origem existem;
- processar pacotes em background;
- limitar cache de imagens da UI;
- invalidar previews por assinatura de arquivo;
- evitar releitura e regravacao desnecessaria de `mappings.json`;
- usar hash em streaming para arquivos aplicados;
- registrar tempos relevantes em `performance.log`.

## 10. O Que O Programa Nao Faz

O Lab Icons Windows nao faz:

- Nao modifica `.exe`, `.dll`, `.mun` ou recursos embutidos.
- Nao quebra nem regrava assinaturas digitais.
- Nao altera `HKLM`, `HKCU\Software\Classes`, `DefaultIcon` ou CLSIDs do sistema.
- Nao muda associacoes globais de extensoes de arquivo.
- Nao troca assets internos de apps UWP instalados.
- Nao edita `AppxManifest.xml`.
- Nao instala servico em background.
- Nao roda como administrador.
- Nao reinicia `explorer.exe` automaticamente.
- Nao apaga `IconCache.db` automaticamente.
- Nao garante controle absoluto sobre cache visual do Windows.
- Nao aplica icones diretamente em arquivos comuns individuais.
- Nao executa scripts, binarios ou comandos dentro de temas importados.
- Nao sincroniza configuracoes entre usuarios ou maquinas.
- Nao promete compatibilidade com temas sem manifesto.

## 11. Formato de Configuracao

Exemplo simplificado:

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
      "id": "uuid",
      "program_name": "Spotify",
      "program_group": "Comunicacao",
      "shortcut_path": "C:\\Users\\user\\Desktop\\Spotify.lnk",
      "target_type": "shortcut",
      "icon_group": "themes\\Meu Tema\\media",
      "source_icon": "icons-in\\themes\\Meu Tema\\media\\spotify.png",
      "ico_path": "icons-out\\ico\\themes\\Meu Tema\\media\\spotify.ico",
      "png_path": "icons-out\\png\\themes\\Meu Tema\\media\\spotify.png",
      "preferred_asset": "ico",
      "original_icon": "C:\\Program Files\\Spotify\\Spotify.exe,0",
      "backup_icon_path": "C:\\Users\\user\\AppData\\Local\\LabIcons\\Backups\\hash-20260427T200000Z.ico",
      "backup_desktop_ini_path": "",
      "backup_created_at": "2026-04-27T20:00:00Z",
      "is_customized": true,
      "known_key": "shortcut:C:\\Users\\user\\Desktop\\Spotify.lnk",
      "auto_reapply": true,
      "theme_name": "Meu Tema"
    }
  ]
}
```

## 12. Testes e Verificacao

Comandos esperados:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall app.py src
.\.venv\Scripts\python.exe app.py --perf-smoke
```

Os testes cobrem:

- pipeline de imagem;
- persistencia;
- leitura e merge de `desktop.ini`;
- descoberta de apps;
- cache de preview;
- importacao segura de temas;
- rejeicao de ZIP inseguro;
- logger de performance;
- comportamento basico de renderizacao e filtros.

## 13. Diretrizes de Evolucao

Mudancas futuras devem preservar estes contratos:

- manter alteracoes reversiveis;
- nao introduzir edicao de binarios;
- nao exigir administrador para o fluxo principal;
- nao executar conteudo importado;
- manter mapeamentos em formato legivel;
- continuar notificando o Shell por APIs nativas;
- medir rotas potencialmente lentas.

Possiveis evolucoes seguras:

- exportar tema a partir de mapeamentos atuais;
- adicionar fuzzy matching revisavel para temas;
- adicionar watcher nativo para `icons-in/`;
- melhorar limpeza opcional de cache com confirmacao explicita;
- adicionar tela dedicada para gerenciar temas importados.
