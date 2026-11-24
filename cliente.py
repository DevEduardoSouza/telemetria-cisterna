#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cliente.py: MÓDULO DE MEDIÇÃO da cisterna (lado CLIENTE).

Passo a passo do que acontece:
  1. Pergunta IP e porta da central e a identificação do ponto de medição.
  2. Conecta por TCP (connect: o "aperto de mão" de 3 vias acontece aqui).
  3. Se identifica com "ID <ponto>" e recebe a capacidade da cisterna.
  4. Envia leituras em um de dois modos:
       - MANUAL: você digita o volume em litros;
       - SIMULAÇÃO: o volume cai sozinho a cada 4 segundos (consumo da escola).
  5. Mostra a resposta da central e, no "sair", fecha a conexão de forma limpa.

Uso:
    python3 cliente.py                       (pergunta tudo)
    python3 cliente.py --ip 192.168.56.10 --porta 5000 --ponto Cisterna_Bloco_A
"""

import argparse                 # lê opções da linha de comando (--ip, --porta, --ponto)
import re                       # expressões regulares: validar e extrair números
import socket                   # API de sockets TCP/IP do sistema operacional
import threading                # thread da simulação + Lock (trava) + Event (sinal)

import comum as c               # protocolo e utilidades compartilhadas com o servidor

INTERVALO_SIMULACAO = 4     # segundos entre uma leitura e outra na simulação


# ============================================================================
# CONEXÃO COM A CENTRAL
# ============================================================================
class ConexaoCentral:
    """Esconde os detalhes do socket: pedir() envia uma linha e espera a resposta."""

    def __init__(self, ip, porta):
        # create_connection = socket(AF_INET, SOCK_STREAM) + connect((ip, porta)).
        # É dentro do connect() que o SO faz o aperto de mão de 3 vias do TCP
        # (SYN, SYN+ACK, ACK). timeout=5: se a central não responder em 5 s,
        # desiste, em vez de travar para sempre com IP errado ou firewall.
        self.sock = socket.create_connection((ip, porta), timeout=5)
        self.sock.settimeout(None)          # conectado: volta a ser bloqueante, sem limite
        self.entrada = c.leitor(self.sock)  # readline() em cima do socket
        # A simulação roda numa thread e o "sair" na thread principal: a trava
        # garante que um pedido e sua resposta não se misturem com outro.
        self.trava = threading.Lock()

    def pedir(self, mensagem):
        """Modelo pedido/resposta: envia UMA linha e espera UMA linha de volta."""
        with self.trava:                # ninguém mais usa o socket até a resposta chegar
            c.enviar(self.sock, mensagem)
            resposta = c.receber(self.entrada)      # bloqueia até a central responder
        if resposta is None:            # EOF: a central fechou o socket
            raise ConnectionError("a central encerrou a conexão")
        return resposta

    def fechar(self):
        """Saída limpa: avisa a central (SAIR), espera o TCHAU e fecha o socket.

        Só matar o programa também derrubaria a conexão, mas o servidor
        descobriria apenas pelo EOF ou por erro. Avisar é o jeito correto.
        """
        try:
            self.pedir(c.CMD_SAIR)      # envia "SAIR", espera "TCHAU"
        except OSError:                 # se a conexão já caiu, não há a quem avisar
            pass
        finally:
            self.entrada.close()
            self.sock.close()           # manda o FIN do TCP: encerra a conexão


# ============================================================================
# EXIBIÇÃO DA RESPOSTA
# ============================================================================
def exibir_resposta(resposta):
    """Pinta cada bloco [ ... ] da resposta com a cor certa e desenha uma barra."""
    # A resposta pode trazer mais de um bloco na mesma linha, por exemplo
    # "[EVENTO: ...] [ALERTA: ...]"; findall() separa cada "[...]".
    blocos = re.findall(r"\[[^\]]*\]", resposta) or [resposta]
    for bloco in blocos:
        # Cor pela gravidade: vermelho > amarelo > ciano (evento) > verde
        if "CRÍTICO" in bloco or "ERRO" in bloco:
            tom = c.VERMELHO
        elif "ALERTA" in bloco:
            tom = c.AMARELO
        elif "EVENTO" in bloco:
            tom = c.CIANO
        else:
            tom = c.VERDE
        print("  Central: " + c.cor(bloco, c.NEGRITO + tom))

    # Procura "(37,5%)" dentro da resposta para desenhar a barra de nível
    achou = re.search(r"\((\d+(?:,\d+)?)%\)", resposta)
    if achou:
        pct = float(achou.group(1).replace(",", "."))
        cheio = round(pct / 5)                      # barra de 20 blocos: cada bloco = 5%
        print(f"  Nível:   [{'█' * cheio}{'░' * (20 - cheio)}] {achou.group(1)}%")


# ============================================================================
# MODO MANUAL
# ============================================================================
def modo_manual(conexao):
    """Devolve True se o usuário digitou 'sair' (encerrar o programa)."""
    print(c.cor("\n--- MODO MANUAL --- digite o volume em litros "
                "('voltar' = menu, 'sair' = encerrar)", c.NEGRITO))
    while True:
        texto = input("volume (L)> ").strip().lower()
        if texto == "sair":
            return True
        if texto == "voltar":
            return False
        if not texto:               # ENTER vazio: ignora
            continue
        # Validação no CLIENTE: só número (inteiro ou com decimal). O servidor
        # valida de novo, mas já evitamos mandar lixo pela rede.
        if not re.fullmatch(r"\d+([.,]\d+)?", texto):
            print(c.cor("  Digite só o número de litros (ex.: 12000).", c.VERMELHO))
            continue
        # Envia "LEITURA 12000" e mostra a linha que a central respondeu
        exibir_resposta(conexao.pedir(f"{c.CMD_LEITURA} {texto}"))


# ============================================================================
# MODO SIMULAÇÃO DE CONSUMO
# ============================================================================
class Simulacao:
    """Thread que envia o volume a cada 4 s e desconta o consumo fixo.

    Duas threads mexem neste objeto ao mesmo tempo:
      - a thread da simulação (rodar): lê o volume, envia, desconta o consumo;
      - a thread principal (teclado): chover() soma litros e parar.set() encerra.
    Por isso o volume só é lido/alterado dentro da trava.
    """

    def __init__(self, conexao, volume, consumo, capacidade):
        self.conexao = conexao
        self.volume = volume
        self.consumo = consumo
        self.capacidade = capacidade
        self.trava = threading.Lock()       # volume é mexido por 2 threads
        self.parar = threading.Event()      # sinal para a thread terminar (começa "desligado")

    def chover(self, litros_chuva):
        """Simula chuva: soma litros (sem passar da capacidade, a cisterna transborda).

        Chamada pela thread do teclado; a trava evita somar no meio de um desconto.
        """
        with self.trava:
            self.volume = min(self.capacidade, self.volume + litros_chuva)

    def rodar(self):
        """Corpo da thread: envia -> mostra -> espera 4 s -> desconta -> repete."""
        while not self.parar.is_set():
            with self.trava:                # lê o volume de forma segura
                atual = self.volume
            try:
                # Pede à central o status do volume atual (sem casas decimais)
                resposta = self.conexao.pedir(f"{c.CMD_LEITURA} {atual:.0f}")
            except OSError as erro:         # a rede caiu no meio da simulação
                print(c.cor(f"\n  Conexão perdida: {erro}", c.VERMELHO))
                self.parar.set()
                break
            print(f"\n[simulação] volume enviado: {c.litros(atual)}")
            exibir_resposta(resposta)

            if atual <= 0:                  # acabou a água: não faz sentido continuar
                print(c.cor("  Cisterna vazia: simulação encerrada. "
                            "Digite 'parar' para voltar ao menu.", c.VERMELHO))
                break
            # wait() é um "sleep" que pode ser interrompido pelo comando parar:
            # dorme até 4 s, mas acorda na hora se parar.set() for chamado.
            # Devolve True quando foi interrompido -> encerra sem esperar os 4 s.
            if self.parar.wait(INTERVALO_SIMULACAO):
                break
            with self.trava:                # desconta o consumo (nunca abaixo de zero)
                self.volume = max(0, self.volume - self.consumo)


def modo_simulacao(conexao, capacidade):
    """Devolve True se o usuário digitou 'sair' (encerrar o programa)."""
    print(c.cor("\n--- MODO SIMULAÇÃO DE CONSUMO ---", c.NEGRITO))
    volume = c.perguntar_numero("Volume inicial (litros)", capacidade, 0, capacidade)
    consumo = c.perguntar_numero(f"Consumo a cada {INTERVALO_SIMULACAO} s (litros)",
                                 max(1, capacidade // 20), 1, capacidade)
    print(f"Comandos: 'chuva <litros>' (ex.: chuva 3000), 'parar' = menu, 'sair' = encerrar\n")

    # A simulação vai para uma thread; a thread principal fica com o teclado.
    # Sem isso, o input() (bloqueante) travaria o envio periódico, ou o sleep
    # travaria o teclado.
    sim = Simulacao(conexao, volume, consumo, capacidade)
    thread = threading.Thread(target=sim.rodar, daemon=True)
    thread.start()

    sair_do_programa = False
    try:
        while True:                 # laço do teclado, em paralelo com a simulação
            texto = input().strip().lower()
            if texto in ("parar", "sair"):
                sair_do_programa = texto == "sair"
                break
            achou = re.fullmatch(r"chuva\s+(\d+)", texto)       # ex.: "chuva 3000"
            if achou:
                sim.chover(int(achou.group(1)))
                print(c.cor(f"  Chuva! +{c.litros(int(achou.group(1)))} entram "
                            f"na próxima leitura.", c.CIANO))
            elif texto:
                print("  Use: chuva <litros>, parar ou sair")
    finally:
        # Encerramento ordenado: avisa a thread (acorda o wait) e espera ela
        # terminar o pedido em andamento, para não fechar o socket no meio de
        # uma resposta.
        sim.parar.set()
        thread.join()
    return sair_do_programa


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================
def main():
    # ---- 1. Configuração: pela linha de comando ou perguntando no terminal --
    parser = argparse.ArgumentParser(description="Módulo de medição da cisterna")
    parser.add_argument("--ip")
    parser.add_argument("--porta", type=int)
    parser.add_argument("--ponto", help="identificação do ponto de medição")
    args = parser.parse_args()

    print(c.cor("=== MÓDULO DE MEDIÇÃO DA CISTERNA ===", c.NEGRITO))
    ip = args.ip or c.perguntar("IP da central (servidor)", "127.0.0.1")
    porta = args.porta or c.perguntar_numero("Porta", c.PORTA_PADRAO, 1, 65535)
    ponto = args.ponto or c.perguntar("Identificação do ponto de medição",
                                      "Cisterna_Bloco_A")
    # O protocolo separa comando e argumento pelo espaço: "ID Bloco A" seria
    # lido errado, então troca espaços por "_".
    ponto = ponto.strip().replace(" ", "_")

    # ---- 2. Conexão TCP (connect) --------------------------------------------
    try:
        conexao = ConexaoCentral(ip, porta)
    except OSError as erro:         # recusada (servidor desligado), timeout, sem rota...
        print(c.cor(f"Não foi possível conectar em {ip}:{porta}: {erro}", c.VERMELHO))
        print("Confira se o servidor está rodando, o IP, a porta e o firewall.")
        return 1

    try:
        # ---- 3. Identificação: a 1ª mensagem do protocolo --------------------
        resposta = conexao.pedir(f"{c.CMD_ID} {ponto}")     # esperado: "OK 16000"
        capacidade = int(resposta.split()[1])               # "OK 16000" -> 16000
        print(c.cor(f"\nConectado à central {ip}:{porta} como '{ponto}'. "
                    f"Capacidade da cisterna: {c.litros(capacidade)}", c.VERDE))

        # ---- 4. Menu: cada modo devolve True quando o usuário pediu 'sair' ---
        while True:
            print(c.cor("\n========== MENU ==========", c.NEGRITO))
            print("  1 - Modo manual (digitar o volume)")
            print(f"  2 - Simulação de consumo (a cada {INTERVALO_SIMULACAO} s)")
            print("  sair - encerrar a transmissão")
            opcao = input("opção> ").strip().lower()
            if opcao == "1":
                if modo_manual(conexao):
                    break
            elif opcao == "2":
                if modo_simulacao(conexao, capacidade):
                    break
            elif opcao == "sair":
                break
            else:
                print("Opção inválida.")
    except (KeyboardInterrupt, EOFError):   # Ctrl+C ou Ctrl+D: ainda assim fecha direito
        print()
    except OSError as erro:                 # a rede caiu no meio da conversa
        print(c.cor(f"\nConexão perdida: {erro}", c.VERMELHO))

    # ---- 5. Encerramento limpo: SAIR -> TCHAU -> close() ---------------------
    conexao.fechar()
    print("Transmissão encerrada. Conexão fechada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
