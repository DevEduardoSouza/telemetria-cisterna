# Roteiro da apresentação (24/11)

Tempo sugerido: **10 a 12 minutos**. A ordem segue a matriz de avaliação:
ambiente (VMs) → funcionamento → código → bônus → perguntas.

---

## 0. Antes de começar (checklist)

- [ ] As duas VMs Debian ligadas e na mesma rede (Bridge ou Rede Interna `intnet`)
- [ ] `ip -4 addr` anotado: servidor = `__________`  cliente = `__________`
- [ ] `ping` do cliente para o servidor funcionando
- [ ] Projeto atualizado nas duas VMs (`git pull`)
- [ ] Apagar o log antigo no servidor: `rm -f log_cisterna.txt`
- [ ] Som da VM ligado (para o apito do alerta crítico)
- [ ] Na VM cliente, **dois terminais** abertos (para mostrar duas cisternas)
- [ ] Repositório aberto no navegador, na aba de **commits**

---

## 1. Abertura (1 min)

> "No semiárido, como aqui em Irecê, a escola depende da água da cisterna até a próxima chuva.
> O projeto simula um sistema de telemetria: o **cliente** é o sensor da cisterna, que mede o volume,
> e o **servidor** é a central que analisa o nível e emite alertas de seca. Toda a comunicação é feita
> com **sockets TCP**, em duas máquinas virtuais Debian diferentes."

Mostre o desenho do README (seção inicial).

---

## 2. Ambiente: VMs e rede (2 min) · vale até 2,0

Cola de uma página para ter na mão: [`docs/COLA-VMS.md`](COLA-VMS.md). O script `ambiente.sh`
imprime tudo que o avaliador precisa ver (Debian, hostname, IPs, ping e sockets TCP da porta 5000);
você só precisa lembrar de rodá-lo.

1. VirtualBox: mostre as **duas VMs** e, em uma delas, Configurações → Rede → Adaptador 2
   (Rede Interna `intnet`).
2. Em cada VM: `bash ambiente.sh`. Aparecem o Debian, o hostname, os IPs `.10` e `.20` e o
   **✔ As VMs se enxergam**.
3. Suba o servidor e conecte o cliente (passos 4 e 5 da cola, ou 3.1 e 3.2 abaixo) e rode
   `bash ambiente.sh` de novo no servidor: aparece
   `ESTABELECIDA 192.168.50.10:5000 <-> 192.168.50.20:xxxxx`.

> "O próprio kernel do servidor mostra a conexão TCP estabelecida entre os dois IPs: são duas
> máquinas independentes na mesma rede, e o servidor escuta em 0.0.0.0 justamente para aceitar
> conexões vindas de fora dele."

> "Por que TCP e não UDP? Porque uma leitura de nível não pode se perder nem chegar fora de ordem:
> o TCP garante entrega, ordem e conexão. Um alerta crítico perdido seria um problema real."

---

## 3. Demonstração (4 min) · vale até 3,0

### 3.1 Servidor (VM 1)

```bash
python3 servidor.py
```

Digite: IP `0.0.0.0`, porta `5000`, capacidade `16000`.

> "0.0.0.0 quer dizer: aceite conexões chegando por qualquer placa de rede desta VM."

### 3.2 Cliente, modo manual (VM 2, terminal 1)

```bash
python3 cliente.py
```

IP do servidor, porta `5000`, ponto `Cisterna_Bloco_A`. Opção `1` e digite, um por vez:

| Digite  | Mostra              | Fala                                              |
| ------- | ------------------- | ------------------------------------------------- |
| `12000` | NORMAL 75%          | "acima de 50%, situação normal"                   |
| `6000`  | MODERADO 37,5%      | > "entre 20 e 49%, consumo consciente"            |
| `2500`  | CRÍTICO 15,6%       | **olhe para o servidor**: apito + quadro vermelho |
| `abc`   | recusado no cliente | "validação no cliente"                            |
| `99999` | `[ERRO: ...]`       | "e validação no servidor, que é quem manda"       |

### 3.3 Cliente, simulação + chuva (VM 2, terminal 2)

```bash
python3 cliente.py --ip <IP_SERVIDOR> --porta 5000 --ponto Cisterna_Bloco_B
```

Opção `2`, volume inicial `9000`, consumo `1000`. Deixe cair por 3 ou 4 leituras (a cada 4 s).
Quando chegar perto de 20%, digite `chuva 4000` → aparece **[EVENTO: Captação de água pluvial detectada]**.

> "Neste momento existem **duas conexões TCP abertas ao mesmo tempo** no servidor, uma para cada
> cisterna. Cada uma é atendida por uma thread."

### 3.4 Painel e log (VM 1)

```
central> status
```

Mostra a última leitura com data/hora e a tabela por ponto. Depois:

```bash
cat log_cisterna.txt
```

### 3.5 Saída limpa

No cliente: `sair`. No servidor aparece `[-] Cisterna_Bloco_A desconectou`.

> "O cliente avisa com SAIR, a central responde TCHAU e os dois fecham o socket. Não é só matar o programa."

---

## 4. Explicação do código (3 min)

Mostre nesta ordem (os arquivos são curtos e comentados):

1. `comum.py`**: o protocolo.**
   > "O TCP é um fluxo de bytes, ele não separa mensagens. Então combinei que cada mensagem é uma
   > linha terminada em `\n`. O `readline()` junta os pedaços até achar o `\n`."
   >  Mostre `enviar()` (usa `sendall`) e `receber()` (string vazia = o outro lado fechou).
2. `servidor.py` **→** `main()`**: o ciclo do socket do servidor.**

   `socket(AF_INET, SOCK_STREAM)` → `bind` → `listen` → thread com o laço do `accept()`.
   > "O `accept()` devolve um socket **novo** para cada cliente; o original continua só escutando."
3. `servidor.py` **→** `atender_cliente()`**: uma thread por cisterna.**

   Lê a linha, separa comando e argumento (`ID`, `LEITURA`, `SAIR`), responde uma linha por pedido.
4. `servidor.py` **→** `classificar()`**: a regra do enunciado.** `>= 50`, `>= 20`, senão crítico.
5. `servidor.py` **→ classe** `Central` **e o** `Lock`**.**
   > "Várias threads mexem no mesmo dicionário e no mesmo arquivo de log. Sem a trava, duas
   > leituras simultâneas podiam se misturar: é a condição de corrida. O `with self.trava:` deixa
   > uma thread por vez na região crítica."
6. `cliente.py` **→** `Simulacao.rodar()`**.**

   Thread que envia, espera 4 s com `Event.wait()` (um sleep que pode ser interrompido pelo
    `parar`) e desconta o consumo. O teclado continua livre para `chuva` e `parar`.

---

## 5. Bônus (30 s) · vale até 2,0

- `log_cisterna.txt` com data, hora, volume, porcentagem e nível ✔
- Detecção de chuva: aumento ≥ 5% da capacidade entre duas leituras do mesmo ponto ✔
- Extras: várias cisternas simultâneas, painel por ponto, validações nos dois lados.

Mostre também o **histórico de commits** no GitHub.

---

## 6. Perguntas prováveis e respostas

**Por que uma thread por cliente?**
Porque `accept()` e `readline()` são **bloqueantes**: se o servidor ficasse esperando a leitura
de uma cisterna, as outras não seriam atendidas. Cada thread espera só a sua.

**O que acontece se o cliente cair sem mandar SAIR?**
O `readline()` devolve string vazia (EOF) ou dá erro de conexão; a thread do cliente termina e
mostra "desconectou". O servidor continua atendendo as outras.

**Por que** `sendall` **e não** `send`**?**
`send` pode enviar só uma parte dos bytes; `sendall` repete até mandar tudo.

**Qual a diferença entre o socket do** `listen` **e o do** `accept`**?**
O primeiro só recebe pedidos de conexão (porta 5000). O do `accept` é a conexão de fato com um
cliente específico (IP e porta de origem do cliente, ex.: `192.168.50.20:56810`).

**Onde está o "aperto de mão" de 3 vias?**
Dentro do `connect()` do cliente e do `accept()` do servidor: o sistema operacional troca
SYN, SYN+ACK e ACK. Dá para ver com `sudo tcpdump -i enp0s8 port 5000`.

**Por que a porcentagem 49,95% vira 50%?**
A porcentagem é arredondada para uma casa decimal **antes** de classificar, para o número
mostrado e o nível sempre baterem.

**Como a central sabe que choveu?**
Ela guarda a última leitura de cada ponto. Se a nova for maior em pelo menos 5% da capacidade
(800 L em 16.000 L), o aumento não pode ser consumo: é recarga pela chuva.

**Por que 0.0.0.0 no servidor?**
Escuta em todas as interfaces. Se usasse `127.0.0.1`, só aceitaria conexões da própria VM.
