# Recuperação autorizada do ESP32

Escopo aprovado pelo proprietário na conversa: substituir o inicializador incorreto na placa, restaurar o firmware da estação e verificar os envios; aplicar qa-orchestrator ao projeto ESP32.

Critérios: preservar credenciais e drivers; não imprimir ou ler credenciais; usar firmware/main.py local como inicializador e preservar estacao.py se idêntico; manter leituras 5 s, envios 7 s, Wi-Fi 10 s, MQ-135 habilitado e ADC bruto; não habilitar ppm sem calibração; confirmar arquivo gravado, execução MicroPython, novos POSTs e dashboard. Não formatar flash nem reinstalar MicroPython.

Indício observado pelo coordenador: mpremote não entrou no raw REPL; abertura pyserial com DTR=False e RTS=False antes de open produziu prompt e resposta SERIAL_OK. O main.py remoto anteriormente começava por importação contextlib do backend; o proprietário informou removê-lo. A inspeção independente deve verificar o estado atual e não presumir que o erro anterior ainda exista.

Riscos: interrupção temporária da coleta, sobrescrita incorreta do inicializador e exposição de configuração. Mitigação: cópia anterior já existente em /tmp/esp32-firmware-check-20261103/main.py, comparação dos arquivos sem ler config.py, alvo serial explicitamente identificado. Transferência e reinício foram expressamente solicitados pelo proprietário. Iniciar o backend local é necessário para a verificação, sem dados simulados em produção.

Classificação: complexidade 2 (interação serial/boot), extensão 2 (placa, API e dashboard), risco 2 (interrupção reversível de coleta), incerteza 2 (estado da placa e linhas de controle). Esforço solicitado high para investigação, correção e revalidação; resolução real do runtime não verificada.
