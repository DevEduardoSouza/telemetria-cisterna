#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
servidor.py: CENTRAL DE CONTROLE da cisterna (lado SERVIDOR).

Passo a passo do que acontece:
  1. Pergunta IP, porta e a capacidade total da cisterna (em litros).
  2. Cria um socket TCP, faz bind() no IP/porta e listen(): fica ESCUTANDO.
  3. accept() aceita cada cisterna (cliente) que conecta e cria uma THREAD só
     para ela; assim várias cisternas podem mandar leituras ao mesmo tempo.
  4. Cada leitura vira porcentagem, depois status/alerta, e volta como resposta.
  5. Enquanto isso, o operador digita comandos no terminal: status, ajuda, sair.

Bônus implementados:
  - log_cisterna.txt: histórico com data, hora e volume de cada leitura;
  - alerta de recarga: aumento repentino do volume = captação de água da chuva.

Uso:
    python3 servidor.py                      (pergunta tudo)
    python3 servidor.py --ip 0.0.0.0 --porta 5000 --capacidade 16000
"""

import argparse                 # lê opções da linha de comando (--ip, --porta, ...)
import socket                   # API de sockets TCP/IP do sistema operacional
import threading                # threads (uma por cliente) e Lock (trava)
from datetime import datetime   # data/hora de cada leitura

import comum as c               # protocolo e utilidades compartilhadas com o cliente

ARQUIVO_LOG = "log_cisterna.txt"

# Aumento de pelo menos 5% da capacidade entre duas leituras do mesmo ponto
# é considerado chuva (numa cisterna de 16.000 L, isso dá 800 L de uma vez).
# Consumo só faz o volume DESCER; uma subida grande só pode ser recarga.
LIMIAR_CHUVA = 0.05


# ============================================================================
# REGRA DE NEGÓCIO: transformar litros em nível
# ============================================================================
def classificar(volume, capacidade):
    """Calcula a porcentagem e decide o nível, conforme o enunciado.

        >= 50%       -> NORMAL
        20% a 49,9%  -> MODERADO
        <  20%       -> CRÍTICO

    Devolve (porcentagem, nivel, texto_da_resposta).
    """
    # Arredonda para UMA casa decimal ANTES de comparar. Assim o número que
    # aparece na resposta e o nível sempre batem: 7.992 L em 16.000 L dá
    # 49,95%, que vira 50,0% e é classificado como NORMAL (e não MODERADO).
    pct = round(volume / capacidade * 100, 1)
    x = c.porcento(pct)         # "62,5" (vírgula, padrão brasileiro)
    if pct >= 50:
        return pct, "NORMAL", f"[STATUS: NORMAL ({x}%)]"
    if pct >= 20:
        return pct, "MODERADO", f"[ALERTA: NÍVEL MODERADO ({x}%) - Consumo consciente]"
    return pct, "CRITICO", f"[ALERTA CRÍTICO: NÍVEL BAIXO ({x}%) - Risco de desabastecimento!]"


# ============================================================================
# ESTADO COMPARTILHADO
# ============================================================================
class Central:
    """Guarda as leituras recebidas. É o ESTADO COMPARTILHADO entre as threads.

    Várias threads (uma por cisterna) podem chamar processar_leitura() ao mesmo
    tempo. Sem a trava (Lock), duas threads poderiam alterar o dicionário e o
    arquivo de log juntas e embaralhar os dados (condição de corrida). Com a
    trava, uma thread espera a outra terminar: uma de cada vez.
    """

    def __init__(self, capacidade):
        self.capacidade = capacidade
        self.trava = threading.Lock()    # protege os dois campos abaixo e o arquivo de log
        self.ultima_leitura = None       # última leitura de qualquer ponto
        self.leituras_por_ponto = {}     # "Cisterna_Bloco_A" -> última leitura dele

    def processar_leitura(self, ponto, volume, endereco):
        """Chamada pela thread de cada cliente a cada LEITURA válida.

        Devolve a linha de resposta que deve ser enviada ao cliente.
        """
        # 1) Regra de negócio: puro cálculo, não mexe em nada compartilhado,
        #    então pode rodar fora da trava (várias threads ao mesmo tempo).
        pct, nivel, resposta = classificar(volume, self.capacidade)
        leitura = {
            "ponto": ponto,
            "volume": volume,
            "pct": pct,
            "nivel": nivel,
            "quando": datetime.now(),       # data/hora do registro (pedido do enunciado)
            "endereco": endereco,
        }

        # 2) REGIÃO CRÍTICA: só UMA thread por vez entra aqui. O 'with' adquire
        #    a trava na entrada e libera na saída, mesmo se acontecer um erro.
        with self.trava:
            # Compara com a leitura anterior DESTE ponto para detectar chuva.
            # Precisa estar dentro da trava: outra thread não pode trocar o
            # dicionário entre o get() e a atribuição logo abaixo.
            anterior = self.leituras_por_ponto.get(ponto)
            aumento = volume - anterior["volume"] if anterior else 0
            choveu = aumento >= LIMIAR_CHUVA * self.capacidade

            self.leituras_por_ponto[ponto] = leitura        # atualiza o estado
            self.ultima_leitura = leitura
            self._gravar_log(leitura, choveu, aumento)      # bônus 1: registro
            self._mostrar_no_terminal(leitura, choveu, aumento)
            # <- fim da região crítica: a trava é liberada aqui

        # 3) Monta a resposta final (fora da trava, só usa variáveis locais).
        #    Se choveu, o EVENTO vai na frente, na MESMA linha, para continuar
        #    valendo a regra "um pedido, uma linha de resposta".
        if choveu:
            resposta = f"[EVENTO: Captação de água pluvial detectada] {resposta}"
        return resposta

    # ---- bônus 1: registro de consumo diário -------------------------------
    def _gravar_log(self, leitura, choveu, aumento):
        """Acrescenta uma linha ao arquivo de log.

        Formato:  data hora | ponto | litros | % | nível
        Modo "a" (append): sempre escreve no FIM, nunca apaga o histórico.
        Só é chamada dentro da trava, então duas threads nunca escrevem ao
        mesmo tempo e as linhas não se misturam.
        """
        quando = leitura["quando"].strftime("%Y-%m-%d %H:%M:%S")
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as log:
            if choveu:          # o evento de chuva ganha uma linha própria
                log.write(f"{quando} | {leitura['ponto']} | EVENTO: Captação de "
                          f"água pluvial detectada (+{c.litros(aumento)})\n")
            log.write(f"{quando} | {leitura['ponto']} | {c.litros(leitura['volume'])} | "
                      f"{c.porcento(leitura['pct'])}% | {leitura['nivel']}\n")

    # ---- saída visual no terminal do servidor ------------------------------
    def _mostrar_no_terminal(self, leitura, choveu, aumento):
        """Mostra a leitura na tela da central, com cor por nível e alertas."""
        hora = leitura["quando"].strftime("%H:%M:%S")
        cores = {"NORMAL": c.VERDE, "MODERADO": c.AMARELO, "CRITICO": c.VERMELHO}
        linha = (f"[{hora}] {leitura['ponto']} -> {c.litros(leitura['volume'])} "
                 f"({c.porcento(leitura['pct'])}%) {leitura['nivel']}")
        print("\n" + c.cor(linha, cores[leitura["nivel"]]))

        if choveu:      # bônus 2: alerta de recarga
            print(c.cor(f"  [EVENTO: Captação de água pluvial detectada] "
                        f"+{c.litros(aumento)} desde a última leitura", c.CIANO))

        if leitura["nivel"] == "CRITICO":
            # Aviso SONORO + VISUAL exigido pelo enunciado.
            # '\a' é o caractere BEL (ASCII 7): faz o terminal apitar.
            print("\a" + c.cor("=" * 62, c.VERMELHO))
            print(c.cor(f"  !!! ALERTA CRÍTICO: {leitura['ponto']} com "
                        f"{c.porcento(leitura['pct'])}% !!!", c.NEGRITO + c.VERMELHO))
            print(c.cor("  Risco de desabastecimento! Acione o abastecimento por carro-pipa.",
                        c.VERMELHO))
            print(c.cor("=" * 62, c.VERMELHO))

    # ---- comando "status" do painel local ----------------------------------
    def mostrar_status(self):
        """Comando 'status' do operador (roda na thread principal, a do teclado)."""
        # Copia o que precisa DENTRO da trava e solta logo em seguida: assim os
        # prints (lentos) acontecem sem segurar as threads dos clientes.
        with self.trava:
            ultima = self.ultima_leitura
            todas = sorted(self.leituras_por_ponto.values(), key=lambda l: l["ponto"])

        print(c.cor("\n------------------ PAINEL DA CENTRAL ------------------", c.NEGRITO))
        print(f"Capacidade configurada: {c.litros(self.capacidade)}")
        if ultima is None:
            print("Nenhuma leitura recebida ainda.")
            return
        # Requisito do enunciado: última leitura com data e hora do registro
        print(c.cor("Última leitura recebida:", c.NEGRITO))
        print(f"  Ponto de medição : {ultima['ponto']}  ({ultima['endereco']})")
        print(f"  Volume           : {c.litros(ultima['volume'])}")
        print(f"  Nível            : {c.porcento(ultima['pct'])}%  {ultima['nivel']}")
        print(f"  Data/hora        : {ultima['quando'].strftime('%d/%m/%Y %H:%M:%S')}")
        if len(todas) > 1:      # extra: com várias cisternas, mostra uma tabela
            print(c.cor("Última leitura de cada ponto:", c.NEGRITO))
            for l in todas:
                print(f"  {l['ponto']:<22} {c.litros(l['volume']):>10}  "
                      f"{c.porcento(l['pct']):>5}%  {l['nivel']:<9} "
                      f"{l['quando'].strftime('%H:%M:%S')}")
        print("-" * 55)


# ============================================================================
# COMUNICAÇÃO: uma thread por cliente
# ============================================================================
def atender_cliente(conexao, endereco, central):
    """Conversa com UMA cisterna até ela mandar SAIR ou a conexão cair.

    Roda numa THREAD própria. 'conexao' é o socket NOVO devolvido pelo
    accept(), ligado só a este cliente; 'endereco' é o (IP, porta) de origem.
    """
    endereco_txt = f"{endereco[0]}:{endereco[1]}"      # ex.: "192.168.56.20:56810"
    ponto = endereco_txt        # até o cliente se identificar com ID
    print(c.cor(f"\n[+] Conexão TCP aceita de {endereco_txt}", c.CINZA))

    try:
        # 'with' garante que o socket e o leitor sejam fechados ao sair do
        # bloco, aconteça o que acontecer (SAIR, erro de rede, cliente caiu).
        with conexao, c.leitor(conexao) as entrada:
            # Laço PEDIDO -> RESPOSTA: lê uma linha, responde uma linha.
            while True:
                mensagem = c.receber(entrada)   # bloqueia até chegar uma linha
                if mensagem is None:            # cliente fechou sem avisar (EOF)
                    break

                # "LEITURA 12000" -> comando="LEITURA", argumento="12000".
                # partition() corta no PRIMEIRO espaço; sem espaço, argumento="".
                comando, _, argumento = mensagem.partition(" ")
                comando = comando.upper()       # aceita "leitura" em minúsculo

                if comando == c.CMD_ID:
                    # 1ª mensagem: o cliente diz quem é. Resposta: "OK <capacidade>",
                    # assim o cliente fica sabendo o tamanho da cisterna.
                    ponto = argumento.strip() or endereco_txt
                    print(c.cor(f"[+] {endereco_txt} identificado como '{ponto}'", c.CINZA))
                    c.enviar(conexao, f"{c.RESP_OK} {central.capacidade}")

                elif comando == c.CMD_LEITURA:
                    # Mensagem principal: valida o número, analisa e responde o status
                    c.enviar(conexao, validar_e_processar(argumento, ponto,
                                                          endereco_txt, central))

                elif comando == c.CMD_SAIR:
                    # Encerramento limpo: confirma com TCHAU e sai do laço;
                    # o 'with' lá em cima fecha o socket (FIN do TCP).
                    c.enviar(conexao, c.RESP_TCHAU)
                    break

                else:
                    # Todo pedido recebe resposta, mesmo um comando inválido;
                    # senão o cliente ficaria travado esperando a linha.
                    c.enviar(conexao, f"[ERRO: comando desconhecido '{comando}']")
    except OSError:                             # conexão resetada, rede caiu...
        pass                                    # só ESTA thread termina; as outras seguem
    print(c.cor(f"\n[-] {ponto} ({endereco_txt}) desconectou", c.CINZA))


def validar_e_processar(argumento, ponto, endereco_txt, central):
    """Valida o volume recebido antes de analisar. Devolve a resposta.

    O cliente já valida, mas o servidor NUNCA confia no que vem da rede:
    qualquer programa pode conectar na porta e mandar qualquer coisa.
    """
    try:
        volume = float(argumento.strip().replace(",", "."))     # "12000" ou "12000,5"
    except ValueError:                                          # "abc", vazio...
        return f"[ERRO: volume inválido '{argumento}'. Envie um número em litros]"
    if volume < 0:
        return "[ERRO: volume não pode ser negativo]"
    if volume > central.capacidade:                 # cisterna não enche acima do tamanho
        return (f"[ERRO: volume acima da capacidade da cisterna "
                f"({c.litros(central.capacidade)})]")
    return central.processar_leitura(ponto, volume, endereco_txt)


def aceitar_conexoes(servidor, central):
    """Laço do accept(): roda numa thread separada para não travar o teclado.

    'servidor' é o socket de ESCUTA (o que fez bind + listen). Ele nunca troca
    dados com ninguém; só entrega conexões novas.
    """
    while True:
        try:
            # accept() bloqueia até um cliente completar o aperto de mão de 3
            # vias (SYN, SYN+ACK, ACK). Devolve um socket NOVO, que é a conexão
            # com aquele cliente, e o endereço (IP, porta) dele. O socket de
            # escuta continua livre para aceitar o próximo.
            conexao, endereco = servidor.accept()
        except OSError:                             # socket fechado no 'sair'
            break
        # Uma thread por cliente: enquanto a thread da cisterna A espera a
        # próxima leitura dela, o accept() já pode aceitar a cisterna B.
        # daemon=True: a thread morre junto com o programa, sem precisar de join().
        threading.Thread(target=atender_cliente, args=(conexao, endereco, central),
                         daemon=True).start()


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================
AJUDA = """Comandos da central:
  status  - mostra a última leitura recebida e a data/hora do registro
  ajuda   - mostra esta lista
  sair    - desliga a central"""


def main():
    # ---- 1. Configuração: pela linha de comando ou perguntando no terminal --
    parser = argparse.ArgumentParser(description="Central de telemetria da cisterna")
    parser.add_argument("--ip")
    parser.add_argument("--porta", type=int)
    parser.add_argument("--capacidade", type=int, help="capacidade total em litros")
    args = parser.parse_args()

    print(c.cor("=== CENTRAL DE CONTROLE: TELEMETRIA DE CISTERNA (Irecê/BA) ===", c.NEGRITO))
    # 0.0.0.0 = escuta em TODAS as placas de rede. Com 127.0.0.1 só aceitaria
    # conexões da própria máquina, e a VM do cliente não conseguiria conectar.
    ip = args.ip or c.perguntar("IP para escutar (0.0.0.0 = todas as placas de rede)",
                                "0.0.0.0")
    porta = args.porta or c.perguntar_numero("Porta", c.PORTA_PADRAO, 1024, 65535)
    capacidade = args.capacidade or c.perguntar_numero(
        "Capacidade total da cisterna (litros)", 16000, 1)

    # ---- 2. Ciclo de vida do socket servidor: socket -> bind -> listen ------
    # AF_INET = IPv4, SOCK_STREAM = TCP (fluxo confiável, ordenado, com conexão)
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permite reabrir a mesma porta logo após fechar o servidor. Sem isso, o
    # SO segura a porta por ~1 min (estado TIME_WAIT) e dá "Address already in use".
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        servidor.bind((ip, porta))      # amarra o socket ao IP e porta locais
    except OSError as erro:             # porta ocupada ou IP que não é desta máquina
        print(c.cor(f"Não foi possível usar {ip}:{porta}: {erro}", c.VERMELHO))
        return 1
    servidor.listen()                   # passa a aceitar pedidos de conexão (fila do SO)

    central = Central(capacidade)       # estado compartilhado entre as threads
    print(c.cor(f"\nCentral escutando em {ip}:{porta}  |  capacidade "
                f"{c.litros(capacidade)}  |  log em {ARQUIVO_LOG}", c.VERDE))
    print(AJUDA + "\n")

    # ---- 3. Thread do accept(): aceita clientes sem bloquear o teclado ------
    aceitador = threading.Thread(target=aceitar_conexoes, args=(servidor, central),
                                 daemon=True)
    aceitador.start()

    # ---- 4. Painel local: a thread principal fica com o teclado -------------
    # Enquanto as threads dos clientes recebem leituras, o operador pode
    # digitar 'status' a qualquer momento.
    try:
        while True:
            comando = input("central> ").strip().lower()
            if comando == "status":
                central.mostrar_status()
            elif comando in ("ajuda", "help", "?"):
                print(AJUDA)
            elif comando == "sair":
                break
            elif comando:
                print("Comando desconhecido. Digite 'ajuda'.")
    except EOFError:            # sem teclado (rodando em segundo plano)
        aceitador.join()        # então só fica atendendo clientes, para sempre
    except KeyboardInterrupt:   # Ctrl+C
        print()

    # ---- 5. Encerramento ----------------------------------------------------
    print("Desligando a central...")
    servidor.close()            # fecha o socket de escuta: o accept() falha e a thread termina
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
