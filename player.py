#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import socket
import time
import argparse
import struct

# ==============================================================================
# Константы, основанные на pdmdata.h (без изменений)
# ==============================================================================
N_OF_PIXELS_PER_PMT = 64
N_OF_KI_PER_PMT = 8
N_OF_SPARE_PER_PMT = 8
N_OF_PMT_PER_ECASIC = 6
N_OF_ECASIC_PER_PDM = 6
N_OF_PMTS_IN_FRAME = N_OF_PMT_PER_ECASIC * N_OF_ECASIC_PER_PDM  # 36
N_OF_FRAMES_D3_V0 = 100

DATA_ONLY_PER_PMT_SIZE_BYTES = N_OF_PIXELS_PER_PMT * 4  # 256 байт
FULL_PMT_L3_GEN_SIZE_BYTES = (
    (N_OF_PIXELS_PER_PMT + N_OF_KI_PER_PMT + N_OF_SPARE_PER_PMT) * 4
) # 320 байт
FRAME_SPB_2_L3_V0_SIZE_BYTES = N_OF_PMTS_IN_FRAME * FULL_PMT_L3_GEN_SIZE_BYTES
Z_DATA_TYPE_SCI_L3_V3_SIZE = 1152064
FRAMES_OFFSET = 28

def main():
    parser = argparse.ArgumentParser(
        description="Проигрыватель файлов D3 Ловозера. Отправляет данные FRAME_SPB_2_L3_V0 по UDP.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Аргументы командной строки остаются без изменений
    parser.add_argument(
        'filename', nargs='?', default=None,
        help='Имя входного файла. Если не указано, чтение производится из stdin.'
    )
    parser.add_argument(
        'destination', type=str,
        help='IP-адрес и порт в формате "ip:port" (например, "127.0.0.1:9090").'
    )
    parser.add_argument(
        'pause', type=int,
        help='Пауза между отправкой пакетов в миллисекундах.'
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Включить отладочный вывод.'
    )
    args = parser.parse_args()

    try:
        ip_addr, port_str = args.destination.split(':')
        port = int(port_str)
        if not (0 < port < 65536):
            raise ValueError("Port number must be between 1 and 65535")
    except ValueError as e:
        print(f"Ошибка: неверный формат адреса или порта '{args.destination}'. {e}", file=sys.stderr)
        sys.exit(1)

    pause_sec = args.pause / 1000.0

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.error as e:
        print(f"Ошибка: не удалось создать сокет: {e}", file=sys.stderr)
        sys.exit(1)

    input_stream = None
    try:
        if args.filename:
            input_stream = open(args.filename, 'rb')
        else:
            input_stream = sys.stdin.buffer
            if args.verbose:
                print("Чтение данных из stdin...", file=sys.stdout)

        total_packets_sent = 0
        record_num = 0

        while True:
            record_data = input_stream.read(Z_DATA_TYPE_SCI_L3_V3_SIZE)
            if not record_data:
                break
            if len(record_data) < Z_DATA_TYPE_SCI_L3_V3_SIZE:
                print(f"Ошибка: входной файл/поток обрезан.", file=sys.stderr)
                break

            record_num += 1
            if args.verbose:
                print(f"\nОбработка записи #{record_num}...")

            for frame_idx in range(N_OF_FRAMES_D3_V0):
                udp_payload = bytearray()
                frame_start_byte = FRAMES_OFFSET + (frame_idx * FRAME_SPB_2_L3_V0_SIZE_BYTES)

                # ### ИЗМЕНЕНИЕ ЗДЕСЬ: Фильтрация PMT по индексам ###
                for pmt_idx in range(N_OF_PMTS_IN_FRAME):
                    # Включаем в пакет только PMT с индексами 12-17 и 30-35
                    if (12 <= pmt_idx <= 17) or (30 <= pmt_idx <= 35):
                        pmt_start_byte = frame_start_byte + (pmt_idx * FULL_PMT_L3_GEN_SIZE_BYTES)
                        pmt_data_only = record_data[pmt_start_byte : pmt_start_byte + DATA_ONLY_PER_PMT_SIZE_BYTES]
                        udp_payload.extend(pmt_data_only)
                
                # Отправляем собранный пакет, если он не пустой
                if udp_payload:
                    sock.sendto(udp_payload, (ip_addr, port))
                    total_packets_sent += 1

                    if args.verbose:
                        print(
                            f"Отправлен кадр N {total_packets_sent} "
                            f"(запись:{record_num}, кадр:{frame_idx+1}) "
                            f"(данные от 12 PMT) размером {len(udp_payload)} байт на {ip_addr}:{port}"
                        )

                time.sleep(pause_sec)

    except FileNotFoundError:
        print(f"Ошибка: файл не найден '{args.filename}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if input_stream and args.filename:
            input_stream.close()
        sock.close()
        if args.verbose:
            print(f"\nЗавершение работы. Всего отправлено пакетов: {total_packets_sent}.")

if __name__ == "__main__":
    main()