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

import argparse
import re
import socket
import threading

import comum as c

INTERVALO_SIMULACAO = 4     # segundos entre uma leitura e outra na simulação


# ============================================================================
# CONEXÃO COM A CENTRAL
# ============================================================================
class ConexaoCentral:
    """Esconde os detalhes do socket: pedir() envia uma linha e espera a resposta."""

    def __init__(self, ip, porta):
        # create_connection = socket() + connect(); timeout só para conectar
        self.sock = socket.create_connection((ip, porta), timeout=5)
        self.sock.settimeout(None)
        self.entrada = c.leitor(self.sock)
        # A simulação roda numa thread e o "sair" na thread principal: a trava
        # garante que um pedido e sua resposta não se misturem com outro.
        self.trava = threading.Lock()

    def pedir(self, mensagem):
        with self.trava:
            c.enviar(self.sock, mensagem)
            resposta = c.receber(self.entrada)
        if resposta is None:
            raise ConnectionError("a central encerrou a conexão")
        return resposta

    def fechar(self):
        """Saída limpa: avisa a central (SAIR), espera o TCHAU e fecha o socket."""
        try:
            self.pedir(c.CMD_SAIR)
        except OSError:
            pass
        finally:
            self.entrada.close()
            self.sock.close()


# ============================================================================
# EXIBIÇÃO DA RESPOSTA
# ============================================================================
def exibir_resposta(resposta):
    """Pinta cada bloco [ ... ] da resposta com a cor certa e desenha uma barra."""
    blocos = re.findall(r"\[[^\]]*\]", resposta) or [resposta]
    for bloco in blocos:
        if "CRÍTICO" in bloco or "ERRO" in bloco:
            tom = c.VERMELHO
        elif "ALERTA" in bloco:
            tom = c.AMARELO
        elif "EVENTO" in bloco:
            tom = c.CIANO
        else:
            tom = c.VERDE
        print("  Central: " + c.cor(bloco, c.NEGRITO + tom))

    achou = re.search(r"\((\d+(?:,\d+)?)%\)", resposta)
    if achou:
        pct = float(achou.group(1).replace(",", "."))
        cheio = round(pct / 5)                      # barra de 20 blocos
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
        if not texto:
            continue
        # O servidor valida de novo, mas já evita mandar lixo pela rede
        if not re.fullmatch(r"\d+([.,]\d+)?", texto):
            print(c.cor("  Digite só o número de litros (ex.: 12000).", c.VERMELHO))
            continue
        exibir_resposta(conexao.pedir(f"{c.CMD_LEITURA} {texto}"))


# ============================================================================
# MODO SIMULAÇÃO DE CONSUMO
# ============================================================================
class Simulacao:
    """Thread que envia o volume a cada 4 s e desconta o consumo fixo."""

    def __init__(self, conexao, volume, consumo, capacidade):
        self.conexao = conexao
        self.volume = volume
        self.consumo = consumo
        self.capacidade = capacidade
        self.trava = threading.Lock()       # volume é mexido por 2 threads
        self.parar = threading.Event()      # sinal para a thread terminar

    def chover(self, litros_chuva):
        """Simula chuva: soma litros (sem passar da capacidade, a cisterna transborda)."""
        with self.trava:
            self.volume = min(self.capacidade, self.volume + litros_chuva)

    def rodar(self):
        while not self.parar.is_set():
            with self.trava:
                atual = self.volume
            try:
                resposta = self.conexao.pedir(f"{c.CMD_LEITURA} {atual:.0f}")
            except OSError as erro:
                print(c.cor(f"\n  Conexão perdida: {erro}", c.VERMELHO))
                self.parar.set()
                break
            print(f"\n[simulação] volume enviado: {c.litros(atual)}")
            exibir_resposta(resposta)

            if atual <= 0:
                print(c.cor("  Cisterna vazia: simulação encerrada. "
                            "Digite 'parar' para voltar ao menu.", c.VERMELHO))
                break
            # wait() é um "sleep" que pode ser interrompido pelo comando parar
            if self.parar.wait(INTERVALO_SIMULACAO):
                break
            with self.trava:
                self.volume = max(0, self.volume - self.consumo)


def modo_simulacao(conexao, capacidade):
    """Devolve True se o usuário digitou 'sair' (encerrar o programa)."""
    print(c.cor("\n--- MODO SIMULAÇÃO DE CONSUMO ---", c.NEGRITO))
    volume = c.perguntar_numero("Volume inicial (litros)", capacidade, 0, capacidade)
    consumo = c.perguntar_numero(f"Consumo a cada {INTERVALO_SIMULACAO} s (litros)",
                                 max(1, capacidade // 20), 1, capacidade)
    print(f"Comandos: 'chuva <litros>' (ex.: chuva 3000), 'parar' = menu, 'sair' = encerrar\n")

    sim = Simulacao(conexao, volume, consumo, capacidade)
    thread = threading.Thread(target=sim.rodar, daemon=True)
    thread.start()

    sair_do_programa = False
    try:
        while True:
            texto = input().strip().lower()
            if texto in ("parar", "sair"):
                sair_do_programa = texto == "sair"
                break
            achou = re.fullmatch(r"chuva\s+(\d+)", texto)
            if achou:
                sim.chover(int(achou.group(1)))
                print(c.cor(f"  Chuva! +{c.litros(int(achou.group(1)))} entram "
                            f"na próxima leitura.", c.CIANO))
            elif texto:
                print("  Use: chuva <litros>, parar ou sair")
    finally:
        sim.parar.set()
        thread.join()       # espera a thread terminar o pedido em andamento
    return sair_do_programa


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================
def main():
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
    ponto = ponto.strip().replace(" ", "_")     # o protocolo separa por espaço

    try:
        conexao = ConexaoCentral(ip, porta)
    except OSError as erro:
        print(c.cor(f"Não foi possível conectar em {ip}:{porta}: {erro}", c.VERMELHO))
        print("Confira se o servidor está rodando, o IP, a porta e o firewall.")
        return 1

    try:
        resposta = conexao.pedir(f"{c.CMD_ID} {ponto}")     # esperado: "OK 16000"
        capacidade = int(resposta.split()[1])
        print(c.cor(f"\nConectado à central {ip}:{porta} como '{ponto}'. "
                    f"Capacidade da cisterna: {c.litros(capacidade)}", c.VERDE))

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
    except (KeyboardInterrupt, EOFError):
        print()
    except OSError as erro:
        print(c.cor(f"\nConexão perdida: {erro}", c.VERMELHO))

    conexao.fechar()
    print("Transmissão encerrada. Conexão fechada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
