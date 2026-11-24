# Telemetria de Cisterna Escolar e Manejo Hídrico

**Disciplina:** Redes de Computadores I · **Tema 8** · **Aluno:** Eduardo Souza
**Tecnologia:** Sockets TCP, arquitetura Cliente-Servidor, Python 3 (só biblioteca padrão)

No semiárido, a água da cisterna da escola precisa durar até a próxima chuva. Este projeto simula
o monitoramento de uma cisterna escolar da região de Irecê (BA):

- o **cliente** é o **módulo de medição** instalado na cisterna: mede (ou simula) o volume de água e
  envia para a central;
- o **servidor** é a **central de controle**: calcula a porcentagem, responde com o status e dispara
  alertas de seca ou de desperdício.

```
   VM 2: Debian (cliente)                         VM 1: Debian (servidor)
  ┌──────────────────────────┐    TCP :5000     ┌──────────────────────────────┐
  │ Módulo de medição        │ ───────────────► │ Central de controle          │
  │ Cisterna_Bloco_A         │  LEITURA 12000   │ capacidade: 16.000 L         │
  │  • modo manual           │ ◄─────────────── │  • calcula a %               │
  │  • simulação (4 s)       │  [STATUS: ...]   │  • alertas + aviso sonoro    │
  └──────────────────────────┘                  │  • status / log / chuva      │
   (pode haver várias cisternas ao mesmo tempo)  └──────────────────────────────┘
```

---

## 1. Funcionalidades

### Servidor (`servidor.py`)
| Requisito | Como foi feito |
|---|---|
| Configuração inicial | Pergunta **IP**, **porta** e **capacidade total** em litros (ex.: 16.000 ou 50.000) |
| Recepção de leituras | Recebe `LEITURA <litros>` de cada cisterna conectada |
| Análise de nível | `≥ 50%` → `[STATUS: NORMAL (X%)]` · `20% a 49%` → `[ALERTA: NÍVEL MODERADO (X%) - Consumo consciente]` · `< 20%` → `[ALERTA CRÍTICO: NÍVEL BAIXO (X%) - Risco de desabastecimento!]` |
| Aviso sonoro/visual | No nível crítico o terminal **apita** (caractere BEL `\a`) e mostra um quadro vermelho |
| Painel local | Comando `status` mostra a **última leitura** com **data/hora**, e a última de cada ponto |
| Validações | Volume não numérico, negativo ou acima da capacidade recebe `[ERRO: ...]`; comando desconhecido também |
| Concorrência | **Uma thread por cliente** + `threading.Lock` protegendo o estado compartilhado e o log |

### Cliente (`cliente.py`)
| Requisito | Como foi feito |
|---|---|
| Conexão | Pergunta **IP**, **porta** e a **identificação do ponto** (ex.: `Cisterna_Bloco_A`) |
| Modo manual | Você digita o volume em litros e ele é transmitido |
| Simulação de consumo | O volume **cai uma quantidade fixa a cada 4 segundos**, simulando o uso da escola |
| Exibição | Mostra a resposta da central colorida + uma barra de nível `[████████░░░░] 40,0%` |
| Saída | `sair` envia `SAIR`, espera o `TCHAU` da central e fecha o socket (encerramento limpo) |

### Recursos opcionais (bônus): os dois foram feitos
- **Registro de consumo diário:** cada leitura é gravada em `log_cisterna.txt` com data, hora, volume,
  porcentagem e nível.
- **Alerta de recarga (chuva):** se o volume de um ponto **sobe 5% da capacidade ou mais** de uma
  leitura para a outra (800 L numa cisterna de 16.000 L), a central responde
  `[EVENTO: Captação de água pluvial detectada]`. Na simulação, digite `chuva 3000` para testar.

---

## 2. Protocolo de aplicação

O TCP entrega um **fluxo de bytes**, sem separar mensagens. Por isso foi definido que **cada mensagem
é uma linha de texto UTF-8 terminada em `\n`**. Para cada pedido do cliente, o servidor responde
**exatamente uma linha**.

| Cliente → Servidor | Significado | Resposta do servidor |
|---|---|---|
| `ID Cisterna_Bloco_A` | Identifica o ponto (primeira mensagem) | `OK 16000` (capacidade em litros) |
| `LEITURA 12000` | Volume medido em litros | `[STATUS: NORMAL (75,0%)]` |
| `LEITURA 6000` | | `[ALERTA: NÍVEL MODERADO (37,5%) - Consumo consciente]` |
| `LEITURA 2500` | | `[ALERTA CRÍTICO: NÍVEL BAIXO (15,6%) - Risco de desabastecimento!]` |
| `LEITURA 5000` (subiu muito) | | `[EVENTO: Captação de água pluvial detectada] [ALERTA: ...]` |
| `LEITURA abc` / `-5` / `99999` | Inválido | `[ERRO: ...]` |
| `SAIR` | Encerrar | `TCHAU` (e os dois lados fecham o socket) |

```
 Cliente                                   Servidor
   │ ── SYN ─────────────────────────────►   │   connect() / accept()
   │ ◄──────────────────────── SYN+ACK ───   │   (aperto de mão de 3 vias do TCP)
   │ ── ACK ─────────────────────────────►   │
   │ ── "ID Cisterna_Bloco_A\n" ─────────►   │
   │ ◄─────────────────────── "OK 16000\n"   │
   │ ── "LEITURA 12000\n" ───────────────►   │   calcula 75% → NORMAL
   │ ◄────────── "[STATUS: NORMAL (75,0%)]\n"│
   │            ... (a cada leitura) ...      │
   │ ── "SAIR\n" ────────────────────────►   │
   │ ◄────────────────────────── "TCHAU\n"   │
   │ ── FIN ──► / ◄── FIN ──                  │   close(): fim da conexão
```

---

## 3. Pré-requisitos

- **2 máquinas virtuais Debian 12** no VirtualBox (ou dois computadores na mesma rede);
- **Python 3.7 ou mais novo**, que **já vem instalado no Debian 12** (versão 3.11). Nenhuma biblioteca
  externa é necessária;
- `git` para baixar o projeto (ou copiar os arquivos por pasta compartilhada/pendrive).

Conferir na VM:
```bash
python3 --version        # Python 3.11.x
sudo apt install -y git  # se ainda não tiver
```

---

## 4. Configuração das VMs no VirtualBox

Há duas formas. Escolha **uma** e configure **as duas VMs iguais**.

### Opção A: Placa em modo Bridge (mais simples, se houver rede/Wi-Fi)
1. VM desligada → **Configurações → Rede → Adaptador 1 → Conectado a: Placa em modo Bridge**.
2. Escolha a placa de rede do computador (Wi-Fi ou cabo) e ligue a VM.
3. Cada VM recebe um IP do roteador. Veja com `ip -4 addr` (ex.: `192.168.0.15`).

### Opção B: Rede Interna (não depende do Wi-Fi da sala)
1. Nas duas VMs: **Configurações → Rede → Adaptador 2 → Habilitar → Conectado a: Rede Interna**,
   nome `intnet` (o Adaptador 1 continua em NAT, para ter internet).
2. Ligue as VMs e veja o nome da placa nova com `ip link` (normalmente `enp0s8`).
3. Defina IPs fixos que **sobrevivem ao reboot** (um arquivo em `interfaces.d`):
   ```bash
   # VM 1 (servidor)
   sudo tee /etc/network/interfaces.d/intnet >/dev/null <<'EOF'
   auto enp0s8
   iface enp0s8 inet static
       address 192.168.50.10/24
   EOF
   sudo ifup enp0s8
   # VM 2 (cliente): mesmo comando, trocando por  address 192.168.50.20/24
   ```
   Se aparecer `already configured`, rode `sudo ifdown enp0s8 && sudo ifup enp0s8`.
   Alternativa rápida, que vale só até reiniciar:
   `sudo ip addr add 192.168.50.10/24 dev enp0s8 && sudo ip link set enp0s8 up`.
4. Opcional, mas ajuda na apresentação: dê nomes diferentes às VMs, para o prompt mostrar
   `usuario@servidor` e `usuario@cliente`:
   ```bash
   sudo hostnamectl set-hostname servidor      # na VM 2 use "cliente"
   sudo sed -i 's/^127.0.1.1.*/127.0.1.1\tservidor/' /etc/hosts
   ```
   Saia e entre de novo no terminal para o prompt atualizar.
5. Quando tudo funcionar, tire um **snapshot** de cada VM (`pronto-apresentacao`). Se algo quebrar
   no dia, é só restaurar.

### Testar a rede antes de rodar o projeto
Em cada VM, dentro da pasta do projeto:
```bash
bash ambiente.sh
```
```
════════════════════════════════════════════════════════════
  AMBIENTE DA VM: servidor
════════════════════════════════════════════════════════════
 Sistema:  Debian GNU/Linux 12 (bookworm)
 Hostname: servidor
 Python:   Python 3.11.2
 Placas de rede (IPv4):
    enp0s3   10.0.2.15/24
    enp0s8   192.168.50.10/24   <- rede interna do projeto
────────────────────────────────────────────────────────────
 Ping para a outra VM (192.168.50.20)...
    ✔ As VMs se enxergam   (3 enviados, 3 recebidos, time=0.412 ms)
────────────────────────────────────────────────────────────
 Sockets TCP na porta 5000 (comando: ss -tan):
    LISTEN        0.0.0.0:5000           (servidor escutando)
    ESTABELECIDA  192.168.50.10:5000     <->  192.168.50.20:56810
════════════════════════════════════════════════════════════
```
O script mostra o Debian, o hostname, os IPs de cada placa, faz `ping` na outra VM e lista os
sockets TCP da porta 5000. A linha `ESTABELECIDA` é a prova, dada pelo próprio kernel, de que são
duas máquinas distintas conversando por TCP. Para mostrar isso na mão, o equivalente é
`ping -c 3 192.168.50.10` e `ss -tan | grep 5000`.

O Debian não vem com firewall ativo; se você tiver ativado o `ufw`, libere a porta:
`sudo ufw allow 5000/tcp`.

---

## 5. Instalação e execução

Python é interpretado, então **não há etapa de compilação**: basta baixar e rodar.

### 5.1 Baixar o projeto (nas duas VMs)
```bash
git clone https://github.com/DevEduardoSouza/telemetria-cisterna.git
cd telemetria-cisterna
```

### 5.2 Rodar o SERVIDOR (VM 1)
```bash
python3 servidor.py
```
```
=== CENTRAL DE CONTROLE: TELEMETRIA DE CISTERNA (Irecê/BA) ===
IP para escutar (0.0.0.0 = todas as placas de rede) [0.0.0.0]:
Porta [5000]:
Capacidade total da cisterna (litros) [16000]: 16000

Central escutando em 0.0.0.0:5000  |  capacidade 16.000 L  |  log em log_cisterna.txt
central>
```
> `0.0.0.0` significa "escutar em todas as placas de rede da VM". ENTER aceita o valor entre colchetes.

### 5.3 Rodar o CLIENTE (VM 2)
```bash
python3 cliente.py
```
```
=== MÓDULO DE MEDIÇÃO DA CISTERNA ===
IP da central (servidor) [127.0.0.1]: 192.168.50.10
Porta [5000]:
Identificação do ponto de medição [Cisterna_Bloco_A]:

Conectado à central 192.168.50.10:5000 como 'Cisterna_Bloco_A'. Capacidade da cisterna: 16.000 L

========== MENU ==========
  1 - Modo manual (digitar o volume)
  2 - Simulação de consumo (a cada 4 s)
  sair - encerrar a transmissão
```

Atalho (sem perguntas), útil na apresentação:
```bash
python3 servidor.py --ip 0.0.0.0 --porta 5000 --capacidade 16000
python3 cliente.py  --ip 192.168.50.10 --porta 5000 --ponto Cisterna_Bloco_A
```

Para mostrar **várias cisternas ao mesmo tempo**, abra outro terminal no cliente e rode com outro
ponto (`--ponto Cisterna_Bloco_B`).

---

## 6. Exemplos de execução

### Modo manual (cliente)
```
opção> 1
--- MODO MANUAL --- digite o volume em litros ('voltar' = menu, 'sair' = encerrar)
volume (L)> 12000
  Central: [STATUS: NORMAL (75,0%)]
  Nível:   [███████████████░░░░░] 75,0%
volume (L)> 6000
  Central: [ALERTA: NÍVEL MODERADO (37,5%) - Consumo consciente]
  Nível:   [████████░░░░░░░░░░░░] 37,5%
volume (L)> 2500
  Central: [ALERTA CRÍTICO: NÍVEL BAIXO (15,6%) - Risco de desabastecimento!]
  Nível:   [███░░░░░░░░░░░░░░░░░] 15,6%
volume (L)> 99999
  Central: [ERRO: volume acima da capacidade da cisterna (16.000 L)]
```

### Simulação de consumo com chuva (cliente)
```
opção> 2
Volume inicial (litros) [16000]: 4000
Consumo a cada 4 s (litros) [800]: 1000
Comandos: 'chuva <litros>' (ex.: chuva 3000), 'parar' = menu, 'sair' = encerrar

[simulação] volume enviado: 4.000 L
  Central: [ALERTA: NÍVEL MODERADO (25,0%) - Consumo consciente]
[simulação] volume enviado: 3.000 L
  Central: [ALERTA CRÍTICO: NÍVEL BAIXO (18,8%) - Risco de desabastecimento!]
chuva 3000
  Chuva! +3.000 L entram na próxima leitura.
[simulação] volume enviado: 5.000 L
  Central: [EVENTO: Captação de água pluvial detectada]
  Central: [ALERTA: NÍVEL MODERADO (31,2%) - Consumo consciente]
parar
```

### Terminal do servidor
```
[+] Conexão TCP aceita de 192.168.50.20:56810
[+] 192.168.50.20:56810 identificado como 'Cisterna_Bloco_B'
[19:09:39] Cisterna_Bloco_B -> 4.000 L (25,0%) MODERADO
[19:09:43] Cisterna_Bloco_B -> 3.000 L (18,8%) CRITICO
==============================================================
  !!! ALERTA CRÍTICO: Cisterna_Bloco_B com 18,8% !!!          (+ apito)
  Risco de desabastecimento! Acione o abastecimento por carro-pipa.
==============================================================
[19:09:47] Cisterna_Bloco_B -> 5.000 L (31,2%) MODERADO
  [EVENTO: Captação de água pluvial detectada] +2.000 L desde a última leitura

central> status
------------------ PAINEL DA CENTRAL ------------------
Capacidade configurada: 16.000 L
Última leitura recebida:
  Ponto de medição : Cisterna_Bloco_B  (192.168.50.20:56810)
  Volume           : 5.000 L
  Nível            : 31,2%  MODERADO
  Data/hora        : 21/11/2026 19:09:47
Última leitura de cada ponto:
  Cisterna_Bloco_A          2.500 L   15,6%  CRITICO   19:09:39
  Cisterna_Bloco_B          5.000 L   31,2%  MODERADO  19:09:47
-------------------------------------------------------
```

### Arquivo `log_cisterna.txt` (gerado no servidor)
```
2026-11-21 19:09:39 | Cisterna_Bloco_B | 4.000 L | 25,0% | MODERADO
2026-11-21 19:09:43 | Cisterna_Bloco_B | 3.000 L | 18,8% | CRITICO
2026-11-21 19:09:47 | Cisterna_Bloco_B | EVENTO: Captação de água pluvial detectada (+2.000 L)
2026-11-21 19:09:47 | Cisterna_Bloco_B | 5.000 L | 31,2% | MODERADO
```

---

## 7. Estrutura do código

```
telemetria-cisterna/
├── servidor.py      # central de controle: bind/listen/accept, thread por cliente, alertas, status, log
├── cliente.py       # módulo de medição: connect, modo manual, simulação (thread), saída limpa
├── comum.py         # protocolo (mensagens, enviar/receber linhas) e utilidades de terminal
├── ambiente.sh      # mostra hostname, IPs, ping e sockets TCP da VM (prova do ambiente distinto)
├── docs/
│   ├── ROTEIRO-APRESENTACAO.md   # roteiro da demonstração e explicação do código
│   └── COLA-VMS.md               # cola de uma página da fase de VMs/rede
└── README.md
```

Ciclo de vida dos sockets usado no projeto:

| Servidor | Cliente |
|---|---|
| `socket(AF_INET, SOCK_STREAM)`: cria socket TCP/IPv4 | `create_connection()`: cria o socket e faz `connect()` |
| `bind((ip, porta))`: reserva IP e porta | |
| `listen()`: passa a aceitar conexões | |
| `accept()`: devolve um **socket novo** para cada cliente | |
| `recv`/`sendall` (via `readline`) na thread do cliente | `sendall` / `readline` |
| `close()` | `SAIR` → `TCHAU` → `close()` |

---

## 8. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `Connection refused` | Servidor não está rodando, ou a porta digitada é outra |
| `timed out` / ping não responde | VMs em redes diferentes, conferir a seção 4 |
| `Address already in use` | Já existe um servidor nessa porta; feche-o ou use outra porta |
| Cliente conecta, mas não em outra VM | Servidor escutando em `127.0.0.1`; use `0.0.0.0` |
