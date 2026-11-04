# Estação meteorológica ESP32

Dashboard acadêmico em HTML, CSS e JavaScript puro, servido pelo FastAPI.
O firmware lê os sensores a cada cinco segundos, envia a última leitura por POST a cada 7 segundos e o navegador consulta a API a cada cinco segundos.

## Por onde começar

1. [Inicie o backend no Ubuntu](#executar-no-ubuntu) e abra o dashboard no próprio computador.
2. [Confira o acesso pela rede local](#acessar-pela-rede-local) e anote o IP do computador.
3. [Preencha a configuração Wi-Fi](#configuração-local-e-credenciais).
4. [Conecte, preserve os arquivos e instale o programa no ESP32](#instalar-o-programa-no-esp32-por-usb).
5. [Valide as leituras e os envios na placa](#confirmar-no-esp32-físico).

O **ESP32 executa somente o firmware MicroPython**. O **computador executa FastAPI e SQLite** e precisa permanecer ligado, com o servidor aberto, para receber os dados. O dashboard pode ser aberto no computador ou no celular. Não copie o backend, o frontend ou o ambiente virtual para a placa.

**Pendência para uma placa nova:** o driver BMP280 usado pela estação não está neste repositório. Preserve/recupere o driver da placa atual antes de apagá-la. Sem esse módulo, o import inicial falha e o programa inteiro não inicia, mesmo que os outros sensores funcionem. O passo a passo abaixo explica como conferir isso.

## Estrutura do projeto

```text
ESP32/
├── .gitignore
├── README.md
├── requirements.txt
├── BackEnd/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── schema.sql
│   ├── storage.py
│   └── data/
│       └── estacao.db            # criado ao iniciar; ignorado pelo Git
├── FrontEnd/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── firmware/
│   ├── main.py                   # inicialização automática do ESP32
│   ├── estacao.py
│   ├── config_example.py
│   ├── config.py                 # local, ignorado pelo Git
│   └── diagnosticos/
│       ├── consultar_medicoes.py
│       ├── dht22.py
│       ├── identificar_bmp280.py
│       ├── test_wifi.py
│       └── teste_pressao.py
└── tests/
    ├── dashboard.test.cjs
    ├── test_backend.py
    └── test_firmware.py
```

Os ambientes `.venv/` e `BackEnd/.venv/`, as pastas `__pycache__/`, a configuração local e os arquivos de ferramentas como `.serena/` permanecem no computador, mas são excluídos pelo [.gitignore](.gitignore). O banco SQLite e seus arquivos auxiliares de transação também são ignorados, assim como caches, bytecode Python/MicroPython, logs e arquivos locais de editor. Os exemplos, testes, dependências e fontes permanecem disponíveis para versionamento.
[BackEnd/__init__.py](BackEnd/__init__.py) identifica o pacote usado pelos imports relativos e deve ser preservado.

Na organização realizada, o índice Git estava vazio e o repositório ainda não tinha commits. Portanto, não houve arquivos rastreados para remover do índice; as exclusões previnem sua inclusão futura. Nenhum histórico Git ou ambiente virtual foi apagado.

## Executar no Ubuntu

Use Python 3.10 ou superior. Na raiz deste projeto:

Se Python/pip/venv ainda não estiverem instalados no Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

No terminal do computador, crie e ative o ambiente e inicie o servidor:

```bash
cd "/home/davi-benucci/Área de trabalho/ESP32"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn BackEnd.main:app --host 0.0.0.0 --port 8000
```

Deixe esse terminal aberto. Para parar o servidor, pressione **Ctrl+C** nele. Use um segundo terminal para configurar e transferir o firmware.
Se o Ubuntu informar que o módulo `venv` não está instalado, confira a instalação de `python3-venv`; instalações alternativas de Python podem exigir o pacote `venv` correspondente à sua versão.
Se o VS Code sinalizar imports de FastAPI/Pydantic não resolvidos, selecione `.venv/bin/python` em **Python: Select Interpreter** após instalar as dependências.
Se a porta 8000 já estiver ocupada pelo backend anterior, encerre aquele processo com Ctrl+C antes de iniciar este comando.
Durante o desenvolvimento, pode-se acrescentar `--reload`; recargas e reinícios preservam as medições no SQLite.

Para silenciar somente os logs de acesso HTTP, acrescente a opção nativa do Uvicorn:

```bash
python -m uvicorn BackEnd.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Os logs de inicialização e de erros continuam habilitados. Não é necessário alterar o nível geral de logging.
Execute os comandos acima na raiz do projeto; alternativamente, passe a raiz com `--app-dir`.
O comando `fastapi dev main.py` dentro de `BackEnd` também continua funcionando quando o FastAPI CLI já estiver instalado: [BackEnd/__init__.py](BackEnd/__init__.py) permite a descoberta do pacote. Não é necessário instalar o CLI para executar com Uvicorn.

- Dashboard no computador: <http://127.0.0.1:8000/dashboard> (redireciona para `/dashboard/`).
- Swagger: <http://127.0.0.1:8000/docs>.
- Consulta JSON: <http://127.0.0.1:8000/medicoes/ultima>.
- Histórico JSON: <http://127.0.0.1:8000/medicoes/historico?periodo=24h&limite=500>.
- Estatísticas JSON: <http://127.0.0.1:8000/medicoes/estatisticas?periodo=24h>.

O frontend é montado usando um caminho relativo à localização de [main.py](BackEnd/main.py), e não ao diretório de execução do processo.
Não é necessário um servidor separado para o frontend, uma configuração CORS ou ferramentas de build.

Antes do primeiro POST, o dashboard informa que ainda não há medições; isso é esperado. Se já existir histórico no banco, ele exibirá a última medição, possivelmente desatualizada.

### Iniciar novamente após reiniciar o computador

Reiniciar o computador encerra o servidor. A ativação do ambiente virtual também vale somente para o terminal em que foi executada; é necessário ativá-lo em cada novo terminal. As dependências já instaladas permanecem no disco.

Depois de concluir a instalação inicial acima, abra um terminal e execute **as três linhas**, na ordem:

```bash
cd "/home/davi-benucci/Área de trabalho/ESP32"
source .venv/bin/activate
python -m uvicorn BackEnd.main:app --host 0.0.0.0 --port 8000
```

Se preferir iniciar sem ativar o ambiente, use diretamente o Python dele:

```bash
cd "/home/davi-benucci/Área de trabalho/ESP32"
./.venv/bin/python -m uvicorn BackEnd.main:app --host 0.0.0.0 --port 8000
```

As duas formas usam o mesmo ambiente `.venv` **da raiz do projeto**. A pasta `BackEnd/.venv/`, se existir neste computador, é outro ambiente; instalar pacotes nela não os instala na `.venv` da raiz. Este guia usa sempre a da raiz, inclusive na transferência USB.

O esperado no terminal é `Application startup complete` e uma mensagem indicando a porta 8000. Deixe-o aberto e acesse <http://127.0.0.1:8000/dashboard/>. Se houver um erro, confira a tabela abaixo; o servidor não iniciou apenas porque o comando foi digitado.

| Erro ao iniciar | Como resolver |
| --- | --- |
| `python: comando não encontrado` | Execute `source .venv/bin/activate` na raiz do projeto, ou use `./.venv/bin/python` como acima |
| `No module named uvicorn`, `fastapi` ou `pydantic` | Instale as dependências na `.venv` da raiz com o comando abaixo |
| `.venv/bin/activate` ou `.venv/bin/python` não encontrado | Confira se está na raiz do projeto; se esse ambiente ainda não existir, siga a instalação inicial com `python3 -m venv .venv` |
| `No module named BackEnd` | Entre na raiz `ESP32/` antes de executar o comando |
| `Address already in use` / porta 8000 ocupada | Encerre com Ctrl+C o servidor anterior no terminal em que ele está rodando; não abra uma segunda instância na mesma porta |

Se o ambiente existir, mas faltar alguma dependência, execute na raiz e depois repita a inicialização:

```bash
./.venv/bin/python -m pip install -r requirements.txt
```

Não é necessário recriar ou apagar o ambiente a cada reinício. A ativação e o uso direto do interpretador são descritos na [documentação do Python sobre ambientes virtuais](https://docs.python.org/3/library/venv.html#how-venvs-work).

O caminho acima corresponde a este computador; ajuste-o se mover o projeto. Não execute `python BackEnd/main.py`: o backend usa imports relativos e deve ser iniciado como pacote pelo comando do Uvicorn.

## Persistência local com SQLite

O backend utiliza `sqlite3`, incluído na biblioteca padrão do Python. Não há dependências novas para instalar nem servidor de banco separado. Na inicialização do FastAPI, cria automaticamente a pasta `BackEnd/data/`, o arquivo `estacao.db`, a tabela e o índice, caso ainda não existam.
O caminho é calculado a partir de [BackEnd/storage.py](BackEnd/storage.py), independentemente do diretório de execução. O usuário que executa o backend precisa ter permissão de escrita nessa pasta.

O esquema está em [BackEnd/schema.sql](BackEnd/schema.sql):

| Coluna de `medicoes` | Tipo SQLite |
| --- | --- |
| `id` | `INTEGER PRIMARY KEY`, gerado pelo banco |
| `temperatura_DHT`, `umidade`, `temperatura_BMP`, `pressao_BMP` | `REAL`, aceitam `NULL` |
| `luminosidade`, `gas` | `INTEGER`, aceitam `NULL` |
| `recebida_em` | `TEXT NOT NULL`, data/hora UTC em ISO 8601 com microssegundos |

Cada POST válido insere uma linha, inclusive quando os valores são idênticos aos anteriores. A resposta `{"status":"recebido"}` só é devolvida após confirmar a transação. Inserções usam parâmetros SQL, com commit em caso de sucesso e rollback em caso de erro; as conexões são fechadas após cada operação.
A inicialização usa `CREATE TABLE IF NOT EXISTS` e `CREATE INDEX IF NOT EXISTS` em uma transação. Não limpa, recria ou substitui registros existentes. Dados que já haviam sido perdidos na fase de armazenamento somente em RAM não podem ser recuperados.

`GET /medicoes/ultima` consulta a última linha inserida pelo `id`, preservando exatamente os seis campos e os três metadados já consumidos pelo dashboard. O identificador não é acrescentado a essa resposta. Antes do primeiro registro, continua retornando `{"status":"sem_medicoes"}`.

`GET /medicoes/historico?periodo=24h&limite=500` retorna uma lista JSON com `id`, os seis campos dos sensores e `recebida_em` em cada item:

- O limite padrão é **100**, com mínimo **1** e máximo **1000**. Valores inválidos recebem HTTP 422.
- A resposta contém no máximo 500 pontos. Com período e limite maior que 1, pontos são selecionados ao longo de todo o intervalo, incluindo o primeiro e o último; sem período, são retornados os mais recentes. Com limite 1, retorna a medição mais recente.
- A ordem é cronológica (mais antiga para mais recente), com `id` crescente como desempate.
- `periodo=5m`, `10m`, `15m`, `1h`, `6h` e `24h` filtram pelo horário UTC do servidor. Sem `periodo`, todo o histórico limitado é consultado.
- O índice `idx_medicoes_recebida_em` cobre essa ordenação; o limite também é passado como parâmetro SQL.
- Um banco sem medições retorna `[]`.

`GET /medicoes/estatisticas?periodo=24h` retorna quantidade e os valores `minima`, `maxima` e `media` de temperatura DHT22/BMP280, umidade e pressão. Valores `NULL` são ignorados; quando uma variável não possui dados, seus três valores permanecem `null`. As consultas são parametrizadas e não há preenchimento artificial.

### Monitoramento e alertas

`GET /alertas/atuais` avalia a última medição armazenada, sem criar eventos no banco. Os limites demonstrativos são: temperatura DHT22 ≥ 30 °C, umidade < 30%, umidade ≥ 80% e comunicação desatualizada após mais de 90 segundos. Para alterá-los, edite as constantes em [BackEnd/config.py](BackEnd/config.py) e reinicie o backend; o limite de comunicação também é usado pelo estado de atualização das medições.

O estado é `NORMAL` quando temperatura e umidade estão disponíveis, recentes e dentro dos limites; `ATENCAO` quando uma condição disponível ultrapassa o limite; e `INDISPONIVEL` quando não há medição recente ou faltam dados para concluir que está normal. Em leituras parciais, alertas das variáveis disponíveis continuam aparecendo e a mensagem identifica as ausentes. Uma medição desatualizada gera aviso de comunicação, sem classificá-la como condição ambiental atual. O endpoint inclui horário UTC, valores e limites; o dashboard apresenta o horário local e atualiza a cada cinco segundos.

Esses limites são exemplos para o projeto acadêmico, não avisos meteorológicos oficiais. O MQ-135 é uma leitura ADC bruta sem calibração para concentração e não participa das regras; pressão absoluta também não gera alerta de tempestade. O sistema não envia notificações externas nem mantém histórico de alertas. Os testes automatizados abaixo verificam os limites, valores nulos, perda de comunicação e recuperação usando banco temporário; para observar com dados reais, consulte `/alertas/atuais` ou a seção **Monitoramento e alertas** após reiniciar o backend.

O dashboard preserva os cartões atuais e acrescenta gráficos SVG de temperatura, umidade e pressão abaixo deles. O seletor oferece 5, 10 e 15 minutos, além de 1, 6 e 24 horas; as consultas são atualizadas sem recarregar a página. Horários UTC são convertidos pelo navegador para o fuso local. Ausências permanecem como lacunas e períodos sem dados exibem uma mensagem informativa. O MQ-135 continua apenas como leitura bruta/`NULL`, sem gráficos, ppm ou índice de qualidade do ar.

Quando há redução de pontos, leituras intermediárias, inclusive eventuais valores nulos, podem não aparecer no gráfico. As estatísticas usam todos os registros do período, sem redução. Para consultar o dashboard, acesse `/dashboard/` pelo servidor FastAPI; abrir o HTML diretamente não fornece os endpoints da API.

A idade é calculada a partir do horário UTC persistido, permitindo detectar medições antigas mesmo após reiniciar o processo. Mantenha o relógio do computador correto; ajustes nele podem alterar a idade calculada. Se o horário estiver atrás do recebimento, a idade é limitada a zero. O limite de desatualização continua sendo **mais de 90 segundos**.

Para preservar o histórico, mantenha o arquivo do banco ao atualizar o projeto. Para um backup simples, encerre o backend e copie o arquivo `estacao.db` para um local seguro antes de reiniciar. O banco não é incluído no Git e não há exclusão automática de medições.
Para reverter apenas o código desta etapa, preserve o banco e use a versão anterior do backend; ela não lê o histórico. Não é necessário apagar o banco para desfazer a alteração do código.

Referências: [sqlite3 do Python](https://docs.python.org/3/library/sqlite3.html) e [inicialização com lifespan no FastAPI](https://fastapi.tiangolo.com/advanced/events/).

## Acessar pela rede local

No computador que executa o backend, consulte os endereços da rede:

```bash
hostname -I
```

Escolha o IPv4 da interface Wi-Fi/Ethernet da mesma rede do celular e do ESP32.
Por exemplo, se for `192.168.15.7`, acesse `http://192.168.15.7:8000/dashboard` no celular.
O endereço `127.0.0.1` aponta para o próprio dispositivo, portanto não serve para acessar o computador a partir do celular ou do ESP32.
Se houver bloqueio, verifique o firewall para a porta TCP 8000 e se o roteador permite comunicação entre dispositivos da rede.
O destino configurado no firmware precisa corresponder ao computador que executa o backend.
Confira o dashboard pelo celular antes de configurar a placa. Use uma rede Wi-Fi de **2,4 GHz** para o ESP32-WROOM-32; o computador pode estar conectado por cabo ou outra banda, desde que os dispositivos consigam se comunicar na mesma rede local.
Se o IP do computador mudar, atualize `URL_MEDICOES` e transfira novamente a configuração à placa. `0.0.0.0` é o endereço de escuta do servidor, não o endereço a preencher no firmware.

### Descobrir os IPs no hotspot do celular ou em outra rede

O IP é atribuído pela rede e pode mudar ao trocar de Wi-Fi, reiniciar o roteador/hotspot ou reconectar os dispositivos. Não existe um IP fixo que possa ser presumido para qualquer celular.

Há dois endereços diferentes para conferir:

| Endereço | Para que serve |
| --- | --- |
| **IP do computador que executa FastAPI** | É o destino em `URL_MEDICOES` e o endereço usado para abrir o dashboard pela rede |
| **IP do ESP32** | Identifica a placa na rede; serve para diagnóstico e não é o destino do POST neste projeto |

#### 1. Conectar os dispositivos à rede escolhida

Para usar o celular como roteador, ative o **hotspot/ponto de acesso Wi-Fi em 2,4 GHz** e conecte o computador a ele. Configure o ESP32 com o nome e a senha desse mesmo hotspot em [firmware/config.py](firmware/config.py). Para outra rede Wi-Fi, o procedimento é o mesmo, usando as credenciais dessa rede.

#### 2. Descobrir o IP do computador no Ubuntu

Depois de conectar o computador à rede escolhida, execute no terminal:

```bash
ip -brief -4 address show up
```

Procure a interface conectada ao hotspot/Wi-Fi, geralmente com nome iniciado por `wl`. Se estiver usando cabo, geralmente começa por `en`. Por exemplo, uma linha **ilustrativa** seria:

```text
wlp3s0    UP    192.168.43.120/24
```

Nesse exemplo, o IP do computador seria **`192.168.43.120`**, sem o `/24`. Não escolha `lo` (`127.0.0.1`) nem interfaces de VPN, contêiner ou máquina virtual. Se houver dúvida, abra **Configurações → Wi-Fi → detalhes da conexão ativa → IPv4** no Ubuntu; os nomes dos menus podem variar.

Com esse IP de exemplo, preencha em [firmware/config.py](firmware/config.py):

```python
URL_MEDICOES = "http://192.168.43.120:8000/medicoes"
```

Substitua pelo IP realmente mostrado no seu computador. Transfira a configuração atualizada para a placa [conforme o roteiro USB](#instalar-o-programa-no-esp32-por-usb) e reinicie o ESP32. Mantenha o backend em execução com `--host 0.0.0.0`.

No celular que fornece o hotspot, tente abrir `http://192.168.43.120:8000/dashboard/`, também substituindo o IP. Se o navegador do próprio celular ou os clientes do hotspot não conseguirem acessar, confira firewall e possíveis restrições de comunicação/isolamento do hotspot. Conseguir navegar na internet não confirma que os dispositivos conseguem conversar entre si.

#### 3. Descobrir o IP recebido pelo ESP32

O firmware informa automaticamente o endereço no monitor serial quando conecta, reconecta ou muda de IP, por exemplo: `[Wi-Fi] Conectado. IP do ESP32: 192.168.43.121`. O endereço é ilustrativo; a mensagem mostra o IP real recebido na rede. Ela não se repete a cada passagem pelo laço.
A função `conectar_wifi()` retorna `(ip, ultima_tentativa)`, com `ip` igual a `None` enquanto não houver conexão. Esse IP identifica a placa e não altera `URL_MEDICOES`, que continua apontando para o computador do backend.

Para consultar manualmente:

Deixe a estação tentar conectar ao Wi-Fi. Depois abra o REPL por USB, como na seção de instalação, e pressione **Ctrl+C** para pausar o monitoramento. No prompt `>>>` da **placa**, execute:

```python
import network
wlan = network.WLAN(network.STA_IF)
print("Wi-Fi conectado:", wlan.isconnected())
print("IP, máscara, gateway e DNS:", wlan.ifconfig())
```

Se `isconnected()` retornar `True`, o **primeiro valor** da tupla é o IP do ESP32. O terceiro é o gateway da rede, normalmente o celular quando ele fornece o hotspot. Nenhum desses dois deve substituir o IP do computador em `URL_MEDICOES`. Se retornar `False`, a placa ainda não tem uma conexão Wi-Fi válida; confira credenciais, banda e sinal antes de usar o endereço mostrado.

Esses comandos apenas consultam a interface; não iniciam uma conexão. Após a consulta, reinicie a estação com EN/RESET se já configurou o início automático, ou execute `import estacao` e `estacao.main()` no REPL. Enquanto o programa estiver pausado, não haverá leituras nem novos envios.

Se houver várias interfaces no computador e você já souber o IP do ESP32, consulte a rota até a placa. Troque o endereço ilustrativo abaixo pelo IP real do ESP32:

```bash
ip -4 route get 192.168.43.121
```

Na resposta, `dev` indica a interface escolhida e `src` indica o IP do computador usado nessa rota. Isso ajuda a conferir se você selecionou a interface correta; não comprova acesso HTTP nem ausência de bloqueios.

**Sempre que trocar de rede:** confira novamente o IP do computador, ajuste SSID/senha e `URL_MEDICOES`, copie [firmware/config.py](firmware/config.py) para a placa e reinicie. O firmware atual usa a URL configurada e não descobre automaticamente o backend.

Referências: [endereços de interfaces no Ubuntu](https://manpages.ubuntu.com/manpages/noble/man8/ip-address.8.html), [consulta de rotas no Ubuntu](https://manpages.ubuntu.com/manpages/noble/man8/ip-route.8.html) e [consulta de conexão e IP no MicroPython](https://docs.micropython.org/en/latest/library/network.WLAN.html).

## Firmware MicroPython

O programa da estação é [firmware/estacao.py](firmware/estacao.py). Os scripts antigos de diagnóstico estão em [firmware/diagnosticos/](firmware/diagnosticos/); o antigo `Estacao.py` foi movido para [consultar_medicoes.py](firmware/diagnosticos/consultar_medicoes.py), distinguindo sua consulta GET do programa principal.

- `INTERVALO_LEITURA_MS = 5000`: lê todos os sensores independentemente do intervalo de envio.
- `INTERVALO_ENVIO_MS = 7000`: envia a leitura mais recente, sem manter fila de medições para retransmitir depois.
- O primeiro envio ocorre assim que o Wi-Fi estiver conectado e houver uma leitura, sem esperar 7 segundos. Após uma queda do Wi-Fi, o retorno também permite envio imediato da leitura disponível.
- `INTERVALO_WIFI_MS = 10000`: espaça tentativas de conexão enquanto a rede está indisponível. `conectar_wifi()` inicia a associação sem um laço de espera; a configuração `reconnects=0` desativa as repetições automáticas ilimitadas do driver.
- `time.ticks_ms()` e `time.ticks_diff()` controlam os intervalos, inclusive ao circular o contador. Não há dependência de RTC, NTP ou data/hora do ESP32.
- Uma pausa de 100 ms mantém o laço cooperativo. Não há `sleep(30)`.
- Cada ciclo de leitura começa com todos os campos em `None`. Falhas de leitura ou inicialização de um sensor mantêm apenas seus campos como `null`, sem reaproveitar valores anteriores. O objeto do sensor com falha é recriado na próxima leitura.
- `enviar_medicoes()` usa `timeout=3` no módulo MicroPython `requests` e fecha as respostas em `finally`, inclusive para códigos HTTP de erro. Falhas não geram tentativas imediatas em sequência; o próximo envio usa a leitura mais recente.

O POST é síncrono e o timeout atua nas operações de socket; não representa um prazo total garantido da requisição. Operações de sensores/rede podem atrasar uma leitura. Os dois intervalos são independentes, mas esta implementação não oferece cadência de tempo real rígida.

### Como interpretar os tempos no terminal

Os logs mostram a duração de cada ciclo de leitura e a duração do POST até receber a resposta HTTP, calculadas com `time.ticks_diff()`. Em caso de falha, mostram o tempo decorrido até o erro. Essas durações não incluem a espera programada entre operações. O dashboard consulta a API a cada 5 segundos, mas só recebe uma nova medição da estação aproximadamente a cada 7 segundos.

Versões anteriores mostravam o valor absoluto de `time.ticks_ms()` em mensagens como `Medições enviadas em 2442008 ms`. Esse número é um contador com referência arbitrária, que pode circular, e **não significa que o POST levou 2442008 ms**. Por exemplo, envios registrados em `2412055` e `2442008` aconteceram com intervalo de `29953 ms`, cerca de 30 segundos. Consulte a [documentação dos ticks do MicroPython](https://docs.micropython.org/en/v1.29.0/library/time.html#time.ticks_ms).

Se aparecer `ETIMEDOUT`, houve uma falha real de comunicação naquela tentativa. Confira a rede compartilhada, o IP do computador em `URL_MEDICOES` e o backend em execução. Se o Uvicorn informar `address already in use`, confira a instância existente em vez de iniciar outra na mesma porta: abra o dashboard e consulte `GET /medicoes/ultima`. HTTP 200 sozinho não comprova uma medição recente; confira também `recebida_em`, `idade_segundos` e `desatualizada`.

### Sensores e pinos

O MQ-135 está habilitado por padrão com `MQ135_HABILITADO = True` e envia a leitura ADC bruta. Para desabilitá-lo, altere a constante para `False`: o programa deixa de acessar o GPIO34 e transmite `"gas": null`. Uma falha de leitura também resulta em `null`.

### Análise experimental do MQ-135 — calibração pendente

#### Modo acadêmico do roteiro

O modo nominal solicitado pelo proprietário aplica diretamente o cálculo do exemplo, sem considerar os parâmetros desconhecidos como se fossem medidos. Execute uma vez `python -m BackEnd.calibrar_mq135 --roteiro` para criar uma referência a partir das cinco últimas medições reais do SQLite, todas recentes e com ADC entre 1 e 4094. O banco é somente lido; o resultado é salvo separadamente em `BackEnd/data/mq135-roteiro.json`, sem sobrescrita nem recalibração automática. São cinco transmissões reais da estação, não as amostras a cada 200 ms do exemplo. O ambiente da referência não é presumido como ar limpo.

Como o firmware transmite ADC de 12 bits, a normalização equivalente à utilizada com `read_u16()/65535` no PDF é `ADC/4095`. No modelo nominal do exemplo, `Rs = (4095/ADC − 1) × 10000 Ω`, `R₀ = média(Rs)/3,6` e a estimativa é `exp((ln(Rs/R₀) − b)/a)`. A tensão nominal de 3,3 V cancela algebricamente nessa expressão do exemplo; isso não comprova a tensão física nem corrige o divisor real. Essa opção não transforma Rs nominal em resistência medida. Os pares de coeficientes são os do roteiro descritos abaixo.

`GET /mq135/analise` retorna `EXPERIMENTAL_ROTEIRO`, os quatro resultados em `gas` e `estimativas_ppm`, `unidade: ppm_estimados`, `identifica_tipo_gas: false`, referência e `validacao_fisica: false`. O dashboard substitui o cartão bruto por CO₂ estimado e apresenta também amônia, álcool e benzeno. O ADC permanece somente como entrada interna da aquisição; os contratos de coleta existentes não mudam e o histórico anterior não é apagado. Leituras ausentes, antigas ou saturadas não geram estimativas. Uma calibração física presente tem prioridade e não é substituída silenciosamente pelo modo nominal se for inválida.

Os números são saídas de quatro curvas aplicadas ao mesmo sinal, não identificação do gás nem quatro medições independentes. O modo nominal não possui uma faixa metrológica validada e não serve para alertas de saúde. A calibração física documentada a seguir permanece como alternativa para quando houver medidas e referência apropriadas.

O MQ-135 usa um material semicondutor cuja resistência varia com a exposição a gases e também com condições ambientais. Um módulo pode oferecer **AO**, tensão analógica ligada ao circuito do sensor, e **DO**, saída digital de comparação com limiar do módulo; o projeto usa AO para preservar variações do sinal. O campo `gas` continua armazenando o ADC bruto, sem representar ppm.

O roteiro fornecido do Prof. Olavo Ito usa `R₀ = média(Rs)/3,6` no exemplo e calcula cada curva com `exp((ln(Rs/R₀) − b)/a)`. Pares `(a, b)`: CO₂ `(-0,42; 1,89)`, NH₃ `(-0,42; 1,15)`, álcool `(-0,40; 1,34)` e benzeno `(-0,38; 1,23)`. São parâmetros acadêmicos, não comprovados para esta placa. O texto do roteiro descreve uma equação de potência com notação diferente do código; a implementação reproduz o código, sem afirmar equivalência. A calibração `3,6` e `RL=10 kΩ` são exemplos, não valores medidos da montagem.

Sem uma curva de calibração ADC por dispositivo, não é correto substituir a tensão real por `ADC/4095 × 3,3 V`: a atenuação e as características reais do ADC precisam ser consideradas. O código do roteiro usa 3,3 V como referência do ADC e tensão do circuito sem incluir o divisor; não foi copiado para esta montagem. Consulte a [documentação da Espressif sobre ADC e calibração](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc/index.html).

O [manual da Winsen](https://www.winsen-sensor.com/d/files/mq135-%28ver1_6%29---manual.pdf) especifica condições de ensaio com tensão de circuito e aquecedor de 5,0 V ± 0,1 V, resistência de carga ajustável e pré-aquecimento superior a 48 horas para o ensaio. Aquecimento não é calibração; não se assume que a montagem real foi medida ou validada.

Para o circuito resistivo simples do fabricante, `Rs = RL × (Vc / Vao − 1)`, sendo `Rs` a resistência sensível, `RL` a carga e `Vc` a alimentação do circuito sensor. Se AO estiver diretamente ligado ao divisor previsto de resistores `Rsuperior` e `Rinferior`, sem buffer ou outra carga relevante, `Vao = Vadc × (Rsuperior + Rinferior) / Rinferior` e a carga efetiva é `RL || (Rsuperior + Rinferior)`. Com dois resistores de 10 kΩ ideais, `Vao = 2 × Vadc`, mas o ramo de 20 kΩ também carrega o circuito; isso depende da topologia real do módulo. Com circuito de saída diferente, as fórmulas não se aplicam sem nova análise.

[BackEnd/mq135.py](BackEnd/mq135.py) contém funções para interpolação ADC entre pontos efetivamente medidos, correção do divisor, `Rs`, razão e curvas. Não extrapola fora dos pontos de calibração ou da faixa de razão validada pelo operador. `GET /mq135/analise` consulta a última leitura real e retorna `PENDENTE` enquanto faltar calibração ou a medição for antiga, nula ou inválida. Não altera os registros. A função `avaliar_adc` também permite recalcular leituras históricas com uma calibração explicitamente escolhida, mas não há endpoint histórico de estimativas: valores antigos só devem ser comparados se a mesma montagem e calibração forem aplicáveis.

Para habilitar futuramente, prepare um JSON local com os campos abaixo preenchidos com **dados medidos**, sem usar valores fictícios. Deixe `validacao_fisica` falso até verificar a montagem e a faixa das curvas. `pontos_adc` são pares `[código ADC, tensão em D34 em volts]`, ordenados e medidos em vários pontos com a atenuação usada; o backend interpola linearmente entre eles, de modo que a adequação dessa aproximação deve ser verificada. `amostras_adc` contém pelo menos cinco leituras coletadas no ambiente de referência. `intervalo_razao_validado` é uma faixa positiva de `Rs/R₀` fundamentada para **todas** as curvas, não fornecida automaticamente pelo roteiro.

```json
{
  "identificacao": "identifique montagem, método e condições",
  "versao_modelo": "olavo-1",
  "validacao_fisica": false,
  "tensao_circuito_v": null,
  "rl_ohms": null,
  "divisor_superior_ohms": null,
  "divisor_inferior_ohms": null,
  "pontos_adc": [],
  "amostras_adc": [],
  "relacao_referencia": null,
  "intervalo_razao_validado": []
}
```

Após preencher e validar os campos, ajuste `validacao_fisica` para `true` e execute, na raiz do projeto, `python -m BackEnd.calibrar_mq135 caminho-do-json`. O comando calcula `R₀ = média(Rs)/relação_de_referência` e cria `BackEnd/data/mq135-calibracao.json`, com parâmetros, amostras, identificação, modelo e data UTC. Ele não sobrescreve um arquivo existente; preserve a calibração anterior antes de substituí-la deliberadamente. Não há recalibração automática nem edição do banco de medições. Para desabilitar, mantenha a validação como `false` no arquivo local ou retire-o após preservá-lo.

Na verificação física, confirme alimentação do aquecedor e do circuito sensor, GND comum e topologia do módulo; meça os dois resistores, RL, AO e D34 com instrumento adequado, garantindo que D34 permaneça dentro das especificações do ESP32. Estabeleça a curva ADC da própria placa e condições conhecidas de referência após estabilização térmica. Registre método, temperatura, umidade e data; obtenha uma faixa sustentada para cada curva antes de definir a faixa comum. Não há compensação validada de temperatura/umidade. O MQ-135 não identifica gases individualmente, e os resultados não são adequados para alertas de saúde ou segurança. Testes de software não validam a montagem física.

Os pinos e parâmetros foram preservados:

| Dispositivo | Configuração |
| --- | --- |
| DHT22 | GPIO4 |
| LDR | GPIO27, entrada digital |
| BMP280 | I2C0, SDA GPIO21, SCL GPIO22, 100 kHz, endereço `0x76`; driver `bmp280.BMP280` e método `read()` existentes |
| MQ-135 habilitado | ADC no GPIO34, `ADC.ATTN_11DB`, método `read()` |

### Configuração local e credenciais

SSID, senha e URL do backend ficam em [firmware/config.py](firmware/config.py), ignorado pelo Git. Em uma nova cópia do projeto, crie o arquivo a partir de [config_example.py](firmware/config_example.py), que contém somente valores de exemplo. Execute os comandos na raiz do projeto; `cp -n` preserva uma configuração que já exista:

```bash
cp -n firmware/config_example.py firmware/config.py
chmod 600 firmware/config.py
```

Edite `WIFI_SSID`, `WIFI_SENHA` e `URL_MEDICOES` com a rede e o endereço do seu backend. O endereço `192.0.2.1` do exemplo é ilustrativo e precisa ser substituído. Mantenha a rota `/medicoes` na URL.
Por exemplo, para um computador com IP `192.168.15.7`, a URL será `http://192.168.15.7:8000/medicoes`. Use seu IP real, mantenha os valores entre aspas como no exemplo e salve o arquivo antes de copiá-lo. Não compartilhe a configuração nem backups da placa que contenham a senha.
O programa principal e os diagnósticos de Wi-Fi/HTTP importam essa configuração. Os testes automatizados usam uma configuração simulada, sem depender das credenciais locais.
Os intervalos, pinos e a opção `MQ135_HABILITADO` continuam no programa principal e não foram alterados nesta organização.

Não instale o pacote `requests` do CPython na placa: utilize o módulo MicroPython já usado no projeto, com suporte ao argumento `timeout`. Uma versão sem esse suporte terá o erro registrado, continuará lendo sensores, mas não conseguirá enviar até usar uma versão compatível. A versão exata instalada na placa e o driver BMP280 precisam ser verificados no hardware.

### Driver BMP280

**O driver BMP280 não foi encontrado no projeto**, incluindo os arquivos ignorados: não há `bmp280.py`, `bmp280.mpy` ou pacote `bmp280/`. Os scripts de identificação e teste não contêm o driver. O import `from bmp280 import BMP280`, o método `read()` e as configurações atuais foram preservados.
Para reproduzir a instalação em outra placa, obtenha o mesmo driver que funciona no ESP32 atual, ou confirme se ele está incluído no firmware da placa. Não foi criado, baixado ou substituído um driver. O `requirements.txt` instala somente as dependências do backend, não os módulos MicroPython.

### Instalar o programa no ESP32 por USB

Os comandos `bash` desta seção são executados **no computador**, em um segundo terminal. Os blocos `python` identificados como REPL são executados **na placa**, pelo terminal serial. Use um cabo USB de dados e feche outros monitores seriais, incluindo o do Thonny, antes de usar `mpremote`.

#### 1. Preparar a ferramenta e identificar a porta

```bash
cd "/home/davi-benucci/Área de trabalho/ESP32"
source .venv/bin/activate
python -m pip install mpremote
mpremote connect list
```

`mpremote` é uma ferramenta do computador para transferir arquivos e acessar o REPL. Não é uma dependência do backend. Na listagem, encontre a porta do ESP32 e substitua o exemplo abaixo pela porta correta:

```bash
ESP_PORT=/dev/ttyUSB0
mpremote connect "$ESP_PORT" repl
```

Pressione **Ctrl+C** para interromper um programa em execução e obter o prompt `>>>`. O banner identifica o MicroPython; no REPL, confira a versão:

```python
import sys
print(sys.implementation)
```

Saia do terminal serial com **Ctrl+]**. Se a placa ainda não tiver MicroPython, siga [a instalação inicial do interpretador](#instalação-inicial-do-micropython-somente-se-necessário) e depois retorne aqui. Não reinstale o interpretador em uma placa que já funciona apenas para atualizar os arquivos `.py`.

Se aparecer `Permission denied` na porta no Ubuntu, confira o grupo com `ls -l "$ESP_PORT"`. Se for `dialout`, execute `sudo usermod -aG dialout "$USER"`, encerre a sessão do Ubuntu e entre novamente. Depois reabra os terminais, ative o ambiente e defina `ESP_PORT` outra vez. Não execute `mpremote` com sudo para contornar isso.

#### 2. Preservar os arquivos atuais da placa

Antes de sobrescrever arquivos, com MicroPython já acessível e fora do REPL:

```bash
umask 077
ESP_BACKUP=$(mktemp -d "$HOME/esp32-backup.XXXXXX")
mpremote connect "$ESP_PORT" fs cp -r : "$ESP_BACKUP/"
printf 'Backup salvo em: %s\n' "$ESP_BACKUP"
mpremote connect "$ESP_PORT" fs ls
```

Confira se a cópia terminou sem erro. O backup fica no computador, fora do repositório, e pode conter senhas. Preserve principalmente `boot.py`, `main.py`, os drivers e a pasta `lib/`, se existirem. Essa cópia salva arquivos do sistema de arquivos; módulos congelados no interpretador não aparecem nela.

Confira os imports necessários sem iniciar a estação:

```bash
mpremote connect "$ESP_PORT" soft-reset exec "from bmp280 import BMP280; import requests, dht, network; print('Imports OK'); print('BMP280.read:', hasattr(BMP280, 'read'))"
```

O esperado é `Imports OK` e `BMP280.read: True`. Isso confirma os imports e a presença do método, mas não testa o sensor nem a assinatura do driver. Se faltar `bmp280`, recupere **o mesmo driver que já funciona**, com eventuais dependências, para a raiz ou `lib/` da placa. Não instale outro pacote apenas porque tem o mesmo nome. Se o módulo estiver congelado no interpretador atual, preserve esse interpretador até obter uma forma de reproduzi-lo.

Se faltar somente `requests`, instale a implementação MicroPython pelo computador com acesso à internet e repita a conferência:

```bash
mpremote connect "$ESP_PORT" mip install requests
```

Preserve uma instalação de `requests` que já funcione. O envio real, no passo 4, confirma também o suporte ao argumento `timeout` usado pela estação. Um `ImportError` nos imports iniciais impede a execução; o tratamento individual de sensores só atua depois que o programa consegue importar seus módulos.

#### 3. Copiar os arquivos da estação

Com [a configuração local preenchida](#configuração-local-e-credenciais), copie somente estes dois arquivos para a raiz da placa:

```bash
mpremote connect "$ESP_PORT" fs cp firmware/config.py :config.py
mpremote connect "$ESP_PORT" fs cp firmware/estacao.py :estacao.py
mpremote connect "$ESP_PORT" fs ls
```

Esses comandos substituem as versões anteriores desses dois arquivos; não apagam o driver nem a pasta `lib/`. Não copie `config_example.py` no lugar de `config.py` e não copie [BackEnd/main.py](BackEnd/main.py) para a placa.

Confira os destinos: `firmware/config.py` deve ser copiado para `:config.py`, e `firmware/estacao.py` para `:estacao.py`. O arquivo de configuração contém somente `WIFI_SSID`, `WIFI_SENHA` e `URL_MEDICOES`, conforme o exemplo; ele não deve conter o programa da estação nem `from config import ...`. O comando `mpremote ... run firmware/estacao.py` executa o programa do computador, mas importa a configuração que está **na placa**; editar a configuração no computador exige copiá-la novamente.

#### 4. Executar manualmente e confirmar o envio

Mantenha o backend aberto no primeiro terminal. No segundo, limpe o estado dos imports e abra o REPL:

```bash
mpremote connect "$ESP_PORT" soft-reset repl
```

No prompt `>>>` da placa, execute:

```python
import estacao
estacao.main()
```

Observe as mensagens seriais e o dashboard por pelo menos dois envios, aproximadamente 7 segundos entre eles. Importar o módulo sozinho não inicia o monitoramento. Pressione **Ctrl+C** para interromper e voltar ao REPL; **Ctrl+]** fecha o terminal serial. Uma ação de transferência/conferência do `mpremote` pode interromper o programa, portanto reinicie a estação após terminar as cópias.

#### 5. Iniciar automaticamente ao ligar a placa

Depois de validar o envio manual, copie [firmware/main.py](firmware/main.py) **para a raiz da placa**. Seu conteúdo é somente:

```python
import estacao
estacao.main()
```

Esse arquivo de inicialização é diferente do [main.py do backend](BackEnd/main.py). Saia do REPL e execute o comando abaixo. Ele **sobrescreve o `main.py` da placa**: confira antes o backup e preserve qualquer inicialização adicional necessária que já existisse nele.

```bash
mpremote connect "$ESP_PORT" fs cp firmware/main.py :main.py
mpremote connect "$ESP_PORT" repl
```

Pressione o botão **EN/RESET** da placa para reiniciar e observe se os envios começam sem digitar comandos. Depois teste desligar e religar a alimentação, mantendo o backend ativo. Não coloque esse laço em `boot.py`; preserve o arquivo de boot existente. A execução automática de `main.py` segue a [sequência de inicialização do MicroPython](https://docs.micropython.org/en/latest/reference/reset_boot.html).

Para atualizar o programa posteriormente, repita as cópias necessárias e reinicie com EN/RESET. Se precisar corrigir uma falha de inicialização, abra `mpremote connect "$ESP_PORT" repl`, pressione Ctrl+C e substitua o arquivo responsável. Ao abrir um novo terminal, ative novamente o ambiente e defina `ESP_PORT` antes dos comandos.

Referências dos comandos: [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) e [instalação de pacotes MicroPython](https://docs.micropython.org/en/latest/reference/packages.html).

### Instalação inicial do MicroPython (somente se necessário)

Esta etapa instala o **interpretador `.bin`**, antes da transferência do programa `.py`. Pule-a se a placa atual já executa MicroPython. **Apagar a flash remove todos os arquivos da placa e o interpretador atual**, incluindo drivers que estejam congelados nele. Uma placa funcional não deve ser apagada sem preservar arquivos e dependências.

Para um ESP32-WROOM-32 com flash de pelo menos 4 MiB, baixe o `.bin` da variante genérica, em **Releases**, na [página oficial ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/). Confira o modelo/capacidade da sua placa antes de escolher; as imagens de ESP32-C3/S3 não correspondem a este modelo. O binário do interpretador não inclui automaticamente o driver BMP280 particular deste projeto.

No segundo terminal do computador, com o ambiente ativo, a porta correta em `ESP_PORT` e os monitores seriais fechados:

```bash
python -m pip install esptool
```

Somente para uma placa nova ou uma reinstalação deliberada, execute os comandos abaixo **um por vez**, conferindo o sucesso antes do próximo. Substitua o caminho ilustrativo pelo `.bin` baixado:

```bash
python -m esptool --chip esp32 --port "$ESP_PORT" erase-flash
python -m esptool --chip esp32 --port "$ESP_PORT" --baud 460800 write-flash 0x1000 "/caminho/ESP32_GENERIC-versao.bin"
```

O endereço `0x1000` corresponde à imagem genérica do ESP32 clássico indicada acima. Pressione EN/RESET após a gravação e volte à etapa 1 de instalação do programa. Se a conexão de gravação falhar, consulte as [orientações oficiais do esptool](https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html); se falhar durante a transferência, tente sem `--baud 460800`. Os comandos usam a sintaxe atual com hífen, documentada pelo [esptool](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/basic-commands.html).

### Problemas comuns ao iniciar

| Sintoma | O que conferir |
| --- | --- |
| Nenhuma porta em `mpremote connect list` | Cabo USB de dados, conexão e porta da placa; cabos somente de alimentação não permitem a transferência |
| Porta ocupada | Fechar Thonny, outro `mpremote` e outros monitores seriais |
| `could not enter raw repl` | Confira se a porta está livre, abra `mpremote connect "$ESP_PORT" repl`, pressione EN/RESET e depois Ctrl+C para obter `>>>`. Saia com Ctrl+] antes de tentar transferir/executar novamente; essa interrupção pausa a estação, portanto reinicie após terminar |
| `ImportError: no module named ...` na placa | Driver BMP280, módulo `requests` e arquivo `config.py` nos caminhos indicados acima |
| `ImportError: can't import name WIFI_SSID` dentro de `config.py` | Confira se o programa da estação foi copiado por engano para `:config.py`. Preserve um backup e reinstale [firmware/config.py](firmware/config.py) como `:config.py`; a configuração deve conter as três variáveis, sem importar a si mesma |
| `ImportError: no module named 'contextlib'` ou `'fastapi'` na placa | Confira se copiou o `main.py` correto: use [firmware/main.py](firmware/main.py). O [main.py do backend](BackEnd/main.py) é executado no computador |
| Placa lê sensores, mas não envia | SSID/senha, Wi-Fi 2,4 GHz, IP real em `URL_MEDICOES`, backend ativo com `--host 0.0.0.0` e acesso pela rede local |
| Erro sobre `timeout` ou `reconnects` | Compatibilidade da versão de MicroPython e do módulo MicroPython `requests`; preserve o backup antes de atualizar dependências |
| Dashboard mostra dados antigos | Consultar `recebida_em` e os logs seriais; API acessível não comprova novos POSTs |
| Placa só funciona após comandos no REPL | Conferir o `main.py` da placa, depois reiniciar com EN/RESET |

### Diagnósticos preservados

| Arquivo | Finalidade |
| --- | --- |
| [consultar_medicoes.py](firmware/diagnosticos/consultar_medicoes.py) | Consulta a última medição por GET; usa a URL da configuração local |
| [dht22.py](firmware/diagnosticos/dht22.py) | Monitoramento isolado de temperatura e umidade no GPIO4 |
| [identificar_bmp280.py](firmware/diagnosticos/identificar_bmp280.py) | Leitura do identificador do sensor I2C no endereço `0x76` |
| [test_wifi.py](firmware/diagnosticos/test_wifi.py) | Teste de conexão Wi-Fi com a configuração local |
| [teste_pressao.py](firmware/diagnosticos/teste_pressao.py) | Leitura isolada de temperatura e pressão com o driver BMP280 existente |

Para executar um diagnóstico, copie o script escolhido para a raiz da placa, ao lado de `config.py` e dos drivers necessários, e execute-o pelo editor/REPL. Pare o monitoramento principal antes de testar os mesmos sensores isoladamente. Esses scripts são ferramentas manuais para MicroPython; a suíte automatizada continua em `tests/`.

O backend considera a comunicação desatualizada após mais de 90 segundos sem receber um POST válido. Esse limite foi preservado com o envio a cada 7 segundos, sem adicionar rate limiting.

APIs consultadas: [temporização MicroPython](https://docs.micropython.org/en/latest/library/time.html), [Wi-Fi no ESP32](https://docs.micropython.org/en/latest/esp32/quickref.html#networking) e [implementação MicroPython de requests](https://github.com/micropython/micropython-lib/blob/master/python-ecosys/requests/requests/__init__.py).

## Indicadores e estados

| Campo | Exibição |
| --- | --- |
| `temperatura_DHT` | °C, uma casa decimal |
| `umidade` | %, uma casa decimal |
| `temperatura_BMP` | °C, duas casas decimais |
| `pressao_BMP` | hPa, duas casas decimais |
| `luminosidade` | `0`: ambiente claro; `1`: ambiente escuro |
| `gas` | Inteiro bruto, sem unidade; `null`: Indisponível |

Campos nulos, omitidos ou de tipo inesperado aparecem como **Indisponível**, sem conversão em zero.
Uma luminosidade diferente de 0 ou 1 também aparece como indisponível.
As leituras do MQ-135 não representam ppm, porcentagem ou índice de qualidade do ar.

- A primeira consulta ocorre ao abrir a página; as demais, a cada cinco segundos.
- Uma consulta que demora mais de quatro segundos é cancelada. Requisições não se sobrepõem.
- `{"status":"sem_medicoes"}` mostra que a estação ainda não enviou dados.
- Falhas de rede, de HTTP ou de resposta mostram um aviso e retiram os valores dos cartões. A consulta seguinte tenta recuperar automaticamente.
- O horário exibido corresponde à última **consulta bem-sucedida pelo navegador**, inclusive quando a API informa que ainda não há medições. Não é o horário da coleta.
- O horário **Último POST recebido** corresponde ao recebimento pelo backend, armazenado em UTC e exibido no horário local do navegador. Não é o horário de coleta nos sensores.
- O dashboard distingue API inacessível, ausência de medições, comunicação recente e medição desatualizada. Após **mais de 90 segundos** sem um POST válido, mantém as últimas leituras com um aviso e uma apresentação visual de dados antigos. Um novo POST válido restaura o estado recente na próxima consulta.
- A idade é calculada no servidor a partir do horário UTC gravado no banco, sem depender do relógio do navegador. Os estados são consultados a cada cinco segundos, portanto o aviso pode aparecer até cinco segundos após o limite.
- Se um backend antigo não fornecer os metadados de comunicação, as leituras continuam aparecendo com a idade indicada como desconhecida. A disponibilidade da API não é usada como prova de conexão da estação.
- O backend mantém o histórico no SQLite. Reiniciar o processo preserva as leituras e o horário do último recebimento. Um único processo do servidor é suficiente para esta estação; cada operação abre sua própria conexão ao banco local.

## Contrato HTTP e validação

`POST /medicoes` continua aceitando os seis campos originais e respondendo HTTP 200 com `{"status":"recebido"}`.
Todos os campos aceitam `null` e permanecem opcionais; um campo omitido é armazenado como `null`, nunca como zero ou como uma leitura anterior.
Os campos de temperatura, pressão e umidade aceitam números JSON finitos, inclusive inteiros.
A umidade deve estar entre 0 e 100, inclusive. A luminosidade deve ser o inteiro 0, 1 ou `null`.
O MQ-135 aceita um inteiro bruto ou `null`, sem conversão em ppm ou índice. O inteiro deve caber nos 64 bits com sinal usados pelo SQLite; isso inclui toda a faixa de leitura do ADC do ESP32.
Strings numéricas, booleanos e valores não finitos não são tratados como medições válidas.
Dados inválidos retornam HTTP 422 com `detail`, sem inserir registros nem renovar o horário da última comunicação válida.

Antes do primeiro POST, `GET /medicoes/ultima` mantém exatamente `{"status":"sem_medicoes"}`.
Depois de um POST, a resposta continua plana e preserva os seis campos, acrescentando apenas os metadados:

```json
{
  "temperatura_DHT": 23.9,
  "umidade": 83.8,
  "temperatura_BMP": 25.57,
  "pressao_BMP": 923.28,
  "luminosidade": 0,
  "gas": null,
  "recebida_em": "2026-11-03T01:00:00Z",
  "idade_segundos": 30.5,
  "desatualizada": false
}
```

O exemplo acima ilustra o contrato; horário e idade são gerados pelo servidor.
`desatualizada` passa a `true` quando `idade_segundos > 90`; exatamente 90 segundos ainda é considerado recente.
Consultar a API não renova esse prazo. Qualquer POST válido, inclusive com sensores nulos ou leituras idênticas às anteriores, registra uma nova comunicação.
Campos adicionais enviados pelo cliente continuam sendo ignorados: o cliente não determina o horário nem o estado de atualização.

## Verificação

Os testes do JavaScript usam apenas módulos nativos do Node.js (18 ou superior); Node não é necessário para executar o dashboard.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/dashboard.test.cjs
```

Os testes Python usam `unittest`, a biblioteca padrão e o Uvicorn já instalado. Os testes do backend configuram um banco em um diretório temporário antes de iniciar o servidor HTTP, em uma porta local livre e independente da porta 8000. Encerram o servidor e removem somente esse diretório temporário ao terminar. O banco real não é criado, apagado nem alterado pelos testes.
Cobrem POST/GET, nulos, campos omitidos, zeros, limites de validação, HTTP 422, horário UTC, atualização após cada POST, limite de 90 segundos, recuperação e entrega do dashboard/Swagger. Também verificam histórico, filtros temporais, limites, ordenação cronológica, estatísticas com `NULL`, estado vazio, uso do índice, criação idempotente, recuperação após uma inserção recusada e preservação dos dados após reiniciar o servidor HTTP.
Um processo Python separado, executado fora da raiz do projeto, confirma a leitura do mesmo banco temporário e a indicação de desatualização após reinício. O relógio é controlado nos testes do limite, sem esperar 90 segundos e sem modificar o servidor da estação em uso.
Os testes JavaScript também cobrem as transições recente/desatualizada, recuperação e compatibilidade com um backend sem metadados.

[tests/test_firmware.py](tests/test_firmware.py) executa a lógica do firmware em CPython com módulos de hardware/rede/configuração simulados. Verifica intervalos independentes, primeiro envio imediato, circulação dos ticks, pinos, falhas parciais, ausência de ADC com MQ-135 desabilitado, fechamento HTTP e recuperação sem retransmitir leituras antigas. Também testa a configuração de exemplo e os diagnósticos de Wi-Fi/HTTP movidos. Esses testes não substituem execução no MicroPython ou no ESP32 físico.

### Confirmar no ESP32 físico

1. Transfira o programa da estação e a configuração local preenchida, mantendo os drivers. Confira no REPL a versão de MicroPython e a disponibilidade de `requests` com `timeout` e `WLAN.config(reconnects=0)`.
2. Ligue o backend e execute a estação. O primeiro POST deve ocorrer logo após a conexão Wi-Fi. Observe no terminal leituras aproximadamente a cada 5 segundos e envios aproximadamente a cada 7 segundos, sem HTTP 422 no backend. A duração exibida em cada log mede somente aquela operação, conforme [a explicação dos tempos](#como-interpretar-os-tempos-no-terminal).
3. Confira `GET /medicoes/ultima`: os seis campos continuam presentes, `gas` deve mostrar a leitura bruta ou `null` em caso de falha, e `recebida_em` deve avançar em cada POST. O dashboard deve mostrar comunicação recente.
4. Simule uma falha de sensor em condições elétricas seguras. Apenas os campos afetados devem virar `null` no envio seguinte; os demais sensores continuam sendo lidos. Ao restabelecer o sensor, os valores devem retornar.
5. Interrompa o Wi-Fi: as leituras devem continuar e as tentativas de conexão ficar espaçadas. Ao restabelecê-lo, o envio deve retornar sem uma rajada de medições antigas.
6. Pare e reinicie o backend, mantendo o Wi-Fi. As falhas HTTP devem aparecer no serial sem encerrar o programa; o próximo intervalo de envio deve recuperar a comunicação.
7. Com a API ativa, pare somente os envios da estação por mais de 90 segundos. Confirme o aviso de desatualização no dashboard; retome o programa e confirme a recuperação.

Para um teste manual, abra o Swagger, envie este corpo para `POST /medicoes` e aguarde até cinco segundos no dashboard:

```json
{
  "temperatura_DHT": 23.9,
  "umidade": 83.8,
  "temperatura_BMP": 25.57,
  "pressao_BMP": 923.28,
  "luminosidade": 0,
  "gas": null
}
```

O POST deve responder `{"status":"recebido"}` e o GET deve devolver os mesmos campos.
O GET também inclui `recebida_em`, `idade_segundos` e `desatualizada`.
Esse teste acrescenta uma linha ao histórico e passa a ser a última medição. O próximo POST do firmware acrescentará outra linha. Para testar persistência manualmente, registre uma medição, reinicie o backend e consulte novamente a última medição e o histórico; os registros devem permanecer disponíveis.
Para testar falha de acesso, pare o backend mantendo o dashboard aberto; reinicie e observe a recuperação.
Para observar o aviso de desatualização com a API acessível, interrompa temporariamente o envio do ESP32 e aguarde mais de 90 segundos desde o último POST; o navegador continua consultando a cada cinco segundos.

## Arquivos

- [BackEnd/main.py](BackEnd/main.py): endpoints e montagem do frontend em `/dashboard`.
- [BackEnd/__init__.py](BackEnd/__init__.py): identificação do pacote para imports e FastAPI CLI.
- [BackEnd/models.py](BackEnd/models.py): modelos Pydantic, validação e esquema de resposta.
- [BackEnd/storage.py](BackEnd/storage.py): conexões SQLite, inserção de medições, última leitura, histórico e cálculo da idade/estado.
- [BackEnd/schema.sql](BackEnd/schema.sql): criação idempotente da tabela e do índice.
- [FrontEnd/index.html](FrontEnd/index.html): estrutura e cartões acessíveis.
- [FrontEnd/style.css](FrontEnd/style.css): tema escuro e layout responsivo.
- [FrontEnd/script.js](FrontEnd/script.js): consulta, formatação, estados, gráficos SVG e estatísticas.
- [tests/dashboard.test.cjs](tests/dashboard.test.cjs): testes de comportamento, timeout e recuperação.
- [tests/test_backend.py](tests/test_backend.py): testes HTTP do backend e do monitoramento.
- [firmware/estacao.py](firmware/estacao.py): sensores, Wi-Fi e envio com intervalos independentes.
- [firmware/main.py](firmware/main.py): entrada MicroPython para iniciar a estação automaticamente ao ligar a placa.
- [firmware/config_example.py](firmware/config_example.py): modelo público de configuração, sem credenciais reais.
- [firmware/diagnosticos/](firmware/diagnosticos/): utilitários manuais preservados.
- [.gitignore](.gitignore): exclusões de configurações locais, ambientes, ferramentas e arquivos gerados.
- [tests/test_firmware.py](tests/test_firmware.py): testes da lógica MicroPython com hardware e tempo simulados.
- [requirements.txt](requirements.txt): versões do backend utilizadas na validação.

A integração utiliza o [StaticFiles documentado pelo FastAPI](https://fastapi.tiangolo.com/tutorial/static-files/).
A validação usa [campos Pydantic](https://docs.pydantic.dev/latest/concepts/fields/) e o controle de logs segue as [opções do Uvicorn](https://uvicorn.dev/settings/#logging).
