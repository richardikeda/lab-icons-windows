# TODO Tecnico - Melhorias do Lab Icons Windows

Este documento consolida melhorias e regras de arquitetura para proximas iteracoes. O objetivo e reduzir pesquisa repetida: cada item indica o que fazer, onde mexer, como implementar e o que nao fazer.

## 0. Regras Globais do Projeto

- Rodar como usuario comum por padrao.
- Nao modificar `.exe`, `.dll`, `.ocx`, `.icl`, `.mun`, `System32`, `WindowsApps` ou arquivos assinados.
- Nao alterar `HKLM`, associacoes globais, `DefaultIcon` ou CLSIDs sem uma feature futura explicitamente separada e com consentimento.
- Aplicar icones somente por:
  - `.lnk` via COM/`IShellLink` ou Windows Script Host;
  - pastas via `desktop.ini`;
  - apps UWP por atalho gerenciado para `shell:AppsFolder\<AppUserModelID>`.
- Guardar configuracoes, logs, cache e backups em pasta do usuario, preferencialmente `%LOCALAPPDATA%\LabIcons`.
- Usar `SHChangeNotify` apos mudancas visuais.
- Manter reversibilidade: toda aplicacao deve registrar icone original, alvo, icone customizado e estado de reaplicacao.

## 1. Prioridade Alta

### 1.1 Migrar dados mutaveis para `%LOCALAPPDATA%`

**Problema:** hoje o projeto usa `config/`, `icons-in/` e `icons-out/` ao lado do app. Isso funciona em desenvolvimento, mas em build instalado em `Program Files` causara erro de permissao.

**Fazer:**

- Criar modulo, sugestao: `src/app_paths.py`.
- Definir caminhos:
  - dev: manter pastas no repo, se executado via `python app.py`;
  - frozen/instalado: usar `%LOCALAPPDATA%\LabIcons\`.
- Mover ou resolver:
  - `config/mappings.json`;
  - `config/performance.log`;
  - `config/icon-cache/`;
  - `config/managed-shortcuts/`;
  - `icons-in/`;
  - `icons-out/`;
  - backups.

**Arquivos afetados:**

- `app.py`
- `src/ui.py`
- `src/mapping_store.py`
- `src/perf_logger.py`
- `src/theme_manager.py`
- `src/startup_manager.py`

**Criterio de aceite:**

- App instalado em pasta somente leitura continua funcionando.
- Nenhum arquivo mutavel e criado em `Program Files`.
- README e `docs/TECHNICAL.md` documentam os caminhos.

### 1.2 Backup real dos icones originais

**Problema:** `mappings.json` guarda a localizacao original, mas nao necessariamente extrai/copia um backup visual `.ico`.

**Fazer:**

- Criar pasta:
  - `%LOCALAPPDATA%\LabIcons\Backups\`
- Ao aplicar icone pela primeira vez:
  - atalhos: ler `IconLocation`; se apontar para `.ico`, copiar; se apontar para `.exe/.dll/.mun`, extrair ICO/PNG de preview e salvar backup;
  - pastas: copiar `desktop.ini` original e registrar icone anterior se existir.
- Adicionar campos ao mapping:
  - `backup_icon_path`
  - `backup_desktop_ini_path`
  - `backup_created_at`
- Usar hash do alvo para nome de backup.

**Arquivos afetados:**

- `src/reapply_service.py`
- `src/shortcut_manager.py`
- `src/folder_manager.py`
- `src/icon_preview.py`
- `src/mapping_store.py`

**Criterio de aceite:**

- Restauracao funciona mesmo se o app original mudar o indice do icone.
- Config mostra original e backup.

### 1.3 Reaplicacao/Watchdog transparente

**Estado atual:** existe `--reapply-once` via Startup.

**Melhoria desejada:**

- Adicionar modo watchdog opcional na bandeja do sistema.
- Nao esconder persistencia. Mostrar claramente na UI.
- Usar inicializacao transparente em HKCU ou Startup do usuario.

**Implementacao sugerida:**

- Novo modo CLI:
  - `app.py --tray-watchdog`
- Novo modulo:
  - `src/tray_watchdog.py`
- Intervalo configuravel:
  - usar `settings.auto_check_seconds`.
- Comportamento:
  - rodar em background;
  - chamar `reapply_changed(store, only_global=True)`;
  - exibir menu de bandeja: Abrir app, Reaplicar agora, Pausar, Sair.

**Dependencia possivel:**

- `pystray` ou alternativa Windows nativa.

**Criterio de aceite:**

- Usuario consegue ativar/desativar.
- Aparece no Gerenciador de Tarefas/Inicializar.
- Nao usa servico, DLL injection ou persistencia oculta.

### 1.4 Rollback global robusto

**Estado atual:** existe remover todos customizados.

**Melhoria:**

- Renomear/fortalecer como "Restaurar todos para o padrao".
- Mostrar contagem antes de executar.
- Gerar relatorio de erros.
- Nao apagar mapeamentos antes de tentar restaurar.

**Arquivos afetados:**

- `src/ui.py`
- `src/reapply_service.py`
- `src/mapping_store.py`

**Criterio de aceite:**

- Restaura atalhos para `original_icon`.
- Remove somente `desktop.ini` criado pelo app ou restaura backup.
- Mantem log dos itens que falharam.

## 2. Prioridade Media

### 2.1 Importacao e aplicacao inteligente de temas

**Estado atual:** importa ZIP/pasta com manifesto e cria alguns mapeamentos.

**Melhorar:**

- Tela dedicada de temas.
- Mostrar:
  - nome do tema;
  - quantidade de PNGs;
  - apps associados;
  - apps nao encontrados;
  - preview antes de aplicar.
- Permitir aplicar tema inteiro de uma vez.
- Permitir escolher destino manual para itens nao encontrados.
- Implementar fuzzy matching com confirmacao.

**Formato de manifesto recomendado:**

```json
{
  "theme": "Tema Escuro",
  "icons": [
    {
      "file": "assets/spotify.png",
      "program": "Spotify",
      "group": "media",
      "program_group": "Comunicacao",
      "target_type": "shortcut",
      "target_path": ""
    }
  ]
}
```

**Regras de seguranca:**

- Rejeitar caminhos absolutos.
- Rejeitar `..`.
- Rejeitar ZIP slip.
- Copiar somente PNG declarado.
- Nunca executar conteudo do pacote.

**Arquivos afetados:**

- `src/theme_manager.py`
- `src/ui.py`
- `src/mapping_store.py`

### 2.2 Drag and drop de PNG sobre destino

**Objetivo:** usuario arrasta um `.png` e solta sobre card de app/pasta.

**Fazer:**

- Verificar suporte no CustomTkinter/Tkinter.
- Se necessario, usar dependencia `tkinterdnd2`.
- Ao soltar:
  - validar extensao `.png`;
  - copiar para `icons-in/imported/` ou processar em origem;
  - gerar ICO em background;
  - selecionar destino;
  - aplicar ou perguntar confirmacao.

**Arquivos afetados:**

- `src/ui.py`
- `src/icon_pipeline.py`

**Criterio de aceite:**

- UI nao trava.
- Arquivo invalido mostra erro claro.
- Drag/drop nao sobrescreve arquivos sem hash ou confirmacao.

### 2.3 Elevacao sob demanda para atalhos globais

**Problema:** atalhos em `C:\ProgramData` podem exigir administrador.

**Regra:**

- Nao pedir admin na abertura do app.
- Tentar como usuario comum.
- Se falhar por permissao, mostrar prompt explicando o alvo.
- Usar `ShellExecute(..., "runas", ...)` apenas para uma acao especifica.

**Implementacao sugerida:**

- Criar helper:
  - `src/elevation.py`
- Criar comando CLI:
  - `app.py --apply-mapping <mapping-id>`
- Processo elevado aplica somente aquele mapping.

**Arquivos afetados:**

- `app.py`
- `src/reapply_service.py`
- `src/shortcut_manager.py`
- `src/ui.py`

**Criterio de aceite:**

- App comum nao exibe escudo/admin.
- Elevacao e opcional, contextual e auditavel.

### 2.4 Cache de thumbnails mais forte

**Estado atual:** existe cache em memoria e cache de preview em arquivo.

**Melhorar:**

- Usar `file_hashing.py` para chave baseada em hash quando custo for aceitavel.
- Manter cache em disco em `%LOCALAPPDATA%\LabIcons\Cache\`.
- Registrar tamanho maximo do cache.
- Adicionar rotina de limpeza LRU.

**Arquivos afetados:**

- `src/icon_preview.py`
- `src/ui.py`
- `src/file_hashing.py`

**Criterio de aceite:**

- Reabrir app reaproveita thumbnails.
- Troca de arquivo invalida preview.
- Cache nao cresce indefinidamente.

## 3. Prioridade Baixa / Futuro

### 3.1 Frontend React

**Observacao:** existe `prototipo-ui/`, mas app atual e CustomTkinter.

**Se migrar para React:**

- Backend Python deve expor API local.
- Servir previews como PNG/base64 via endpoint local.
- Processamento em lote deve reportar progresso.
- UI deve ter barra de progresso real.

**Nao fazer agora sem decisao arquitetural:**

- Manter duas UIs completas em paralelo.
- Introduzir servidor local sem necessidade clara.

### 3.2 Instalador profissional

**Objetivo:** gerar app instalavel e confiavel.

**Build Python:**

- PyInstaller ou Nuitka.
- Incluir assets e, se React for usado, `prototipo-ui/dist`.

**Instalador:**

- Usar Inno Setup.
- Instalar em:
  - `C:\Program Files\LabIcons`
- Criar atalhos:
  - Menu Iniciar;
  - opcional Desktop.
- Registrar desinstalador.

**Dados mutaveis:**

- Sempre em `%LOCALAPPDATA%\LabIcons`.

**Criterio de aceite:**

- Usuario nao precisa instalar Python.
- Uninstall remove binarios instalados.
- Dados do usuario so removidos se usuario confirmar.

### 3.3 Assinatura de codigo

**Objetivo:** reduzir alertas SmartScreen/Defender.

**Fazer:**

- Comprar certificado de code signing.
- Assinar:
  - `.exe` gerado;
  - `setup.exe`.
- Usar `signtool.exe`.

**Observacao:**

- SmartScreen depende tambem de reputacao. Certificado EV melhora muito, mas custa mais.

## 4. APIs e Padroes Windows a Usar

### Pastas

Usar `desktop.ini`:

```ini
[.ShellClassInfo]
IconResource=C:\Caminho\Para\Icone.ico,0
```

Tambem aceitavel gravar:

```ini
IconFile=C:\Caminho\Para\Icone.ico
IconIndex=0
```

Obrigatorio:

- pasta com atributo `Read-only` ou `System`;
- `desktop.ini` com `Hidden` e `System`;
- chamar `SHChangeNotify`.

### Atalhos `.lnk`

Usar COM:

- `IShellLink.SetIconLocation(path, index)`;
- `IPersistFile.Save()`;
- ou `win32com.client.Dispatch("WScript.Shell").CreateShortCut`.

### Executaveis

Nunca editar recurso do `.exe`.

Correto:

- criar `.lnk` para o `.exe`;
- aplicar icone no `.lnk`.

### UWP/AppX

Nunca alterar `C:\Program Files\WindowsApps` ou `AppxManifest.xml`.

Correto:

```text
explorer.exe shell:AppsFolder\<AppUserModelID>
```

Aplicar icone no atalho gerenciado.

### Refresh do Shell

Usar `SHChangeNotify`:

- item especifico: `SHCNE_UPDATEITEM`;
- pasta: `SHCNE_UPDATEDIR`;
- associacoes globais somente se uma feature futura realmente alterar associacoes.

## 5. O Que Nao Fazer

- Nao editar `shell32.dll`, `imageres.dll`, `.mun` ou DLLs de apps.
- Nao alterar arquivos em `C:\Windows`.
- Nao alterar arquivos em `C:\Program Files\WindowsApps`.
- Nao pedir UAC na inicializacao.
- Nao salvar banco/log/cache em `Program Files`.
- Nao executar scripts de temas.
- Nao instalar servico oculto.
- Nao usar persistencia escondida.
- Nao reiniciar Explorer automaticamente sem consentimento.
- Nao apagar `IconCache.db` automaticamente.
- Nao modificar Registro global para trocar icones de apps.

## 6. Checklist para Proximo Agente

Antes de codar:

- Ler `README.md`.
- Ler `docs/TECHNICAL.md`.
- Ler este arquivo.
- Verificar `git status --short`.
- Rodar testes existentes se a mudanca for comportamental.

Ao implementar:

- Manter mudancas pequenas por topico.
- Atualizar `mappings.json` schema com defaults retrocompativeis.
- Adicionar teste para cada regra nova.
- Atualizar README e docs quando mudar comportamento.

Validacao minima:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall app.py src
.\.venv\Scripts\python.exe app.py --perf-smoke
```

## 7. Ordem Recomendada de Execucao

1. Criar `app_paths.py` e migrar dados mutaveis para `%LOCALAPPDATA%`.
2. Implementar backups reais de icones originais.
3. Fortalecer rollback global.
4. Evoluir importacao/aplicacao de temas com tela dedicada.
5. Adicionar watchdog em bandeja.
6. Adicionar elevacao sob demanda.
7. Melhorar cache de thumbnails em disco.
8. Avaliar drag and drop.
9. Preparar instalador.
10. Planejar assinatura de codigo.
