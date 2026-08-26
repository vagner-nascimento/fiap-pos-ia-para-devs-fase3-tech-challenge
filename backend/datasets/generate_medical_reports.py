"""Gera laudos médicos sintéticos em PDF, no formato dos exemplos da Mais Laudo."""

from __future__ import annotations

import random
import string
from datetime import date, datetime, timedelta
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph

OUTPUT_DIR = Path(__file__).resolve().parent / "medical_report"
COUNT = 500
SEED = 20260826

BLUE = HexColor("#5B9BD5")
BLUE_DARK = HexColor("#2E5A88")
GRAY = HexColor("#555555")
LIGHT_GRAY = HexColor("#F2F4F7")
GREEN = HexColor("#1B7A4A")
GOLD = HexColor("#C4A035")

NOMES_M = [
    "Caio Belmonte", "Heitor Alencar Prado", "Murilo Quintela", "Davi Noronha Vale",
    "Otávio Leme Siqueira", "Breno Tavares Lins", "Iago Pimentel Rios", "Enzo Galvão Dutra",
    "Rafael Moura Pacheco", "Thiago Farias Nunes", "Lucas Amarante", "Pedro Vilela Campos",
    "André Saldanha Cruz", "Felipe Guimarães Lobo", "Gustavo Penna Rocha", "Henrique Bastos Melo",
    "Igor Vasques Pinto", "João Cândido Freitas", "Leandro Paiva Ramos", "Marcelo Teles Braga",
    "Nicolas Azevedo Pires", "Paulo Henrique Lacerda", "Renato Queiroz Dias", "Samuel Fontes Lima",
    "Victor Hugo Cordeiro", "Wagner Monteiro Reis", "Yuri Albuquerque", "Cauã Bernardes",
    "Eduardo Falcão Neves", "Fabrício Guedes Antunes",
]
NOMES_F = [
    "Helena Vasconcelos", "Isadora Pimentel", "Valentina Correia Luz", "Larissa Mendonça Paiva",
    "Beatriz Furtado Nogueira", "Camila Esteves Rangel", "Daniela Borges Lins", "Elisa Monteiro Cunha",
    "Fernanda Aguiar Prado", "Gabriela Tavares Melo", "Heloísa Quintanilha", "Ingrid Sampaio Reis",
    "Júlia Cavalcante Dias", "Karina Lobato Pires", "Letícia Navarro Gomes", "Marina Peixoto Alves",
    "Natália Ribeiro Campos", "Olivia Farias Dutra", "Patrícia Moura Sena", "Rafaela Nunes Brito",
    "Sabrina Teixeira Lopes", "Tatiane Amaral Costa", "Úrsula Bernardes Pinto", "Vanessa Lacerda Cruz",
    "Yasmin Figueiredo", "Aline Guimarães Rocha", "Bruna Siqueira Vale", "Cíntia Alencar Ramos",
    "Débora Penna Freitas", "Érica Bastos Antunes",
]
SOBRENOMES_EXTRA = [
    "Figueira", "Caldeira", "Maranhão", "Serpa", "Vilar", "Damásio", "Portella", "Goulart",
    "Xavier", "Camargo", "Barreto", "Leal", "Fagundes", "Mesquita", "Andrade", "Coutinho",
]
MEDICOS = [
    ("Dr. Renan Vasques Lobo", "M", "Radiologista"),
    ("Dra. Helena Mendonça Paiva", "F", "Radiologista"),
    ("Dr. Otávio Belmonte Cruz", "M", "Radiologista"),
    ("Dra. Camila Quintela Reis", "F", "Neurologista"),
    ("Dr. Murilo Siqueira Nunes", "M", "Neurologista"),
    ("Dra. Isadora Pimentel Vale", "F", "Neurologista"),
    ("Dr. Thiago Alencar Prado", "M", "Cardiologista"),
    ("Dra. Larissa Furtado Melo", "F", "Cardiologista"),
    ("Dr. Felipe Guimarães Dias", "M", "Cardiologista"),
    ("Dra. Beatriz Navarro Gomes", "F", "Pneumologista"),
    ("Dr. André Saldanha Rocha", "M", "Pneumologista"),
    ("Dra. Fernanda Aguiar Lins", "F", "Oftalmologista"),
    ("Dr. Gustavo Penna Campos", "M", "Oftalmologista"),
    ("Dra. Elisa Monteiro Brito", "F", "Radiologista"),
    ("Dr. Paulo Henrique Lacerda", "M", "Cardiologista"),
]
CIDADES = [
    ("Ananindeua", "PA"), ("Vila Velha", "ES"), ("Belo Horizonte", "MG"), ("Campinas", "SP"),
    ("Recife", "PE"), ("Curitiba", "PR"), ("Porto Alegre", "RS"), ("Salvador", "BA"),
    ("Fortaleza", "CE"), ("Goiânia", "GO"), ("Florianópolis", "SC"), ("Ribeirão Preto", "SP"),
    ("Uberlândia", "MG"), ("Manaus", "AM"), ("Belém", "PA"), ("Natal", "RN"),
    ("João Pessoa", "PB"), ("Campo Grande", "MS"), ("Teresina", "PI"), ("Vitória", "ES"),
    ("São Luís", "MA"), ("Maceió", "AL"), ("Aracaju", "SE"), ("Cuiabá", "MT"),
]
CONVENIOS = ["SUS", "PARTICULAR", "UNIMED", "AMIL", "BRADESCO SAÚDE", "HAPVIDA", "SULAMÉRICA", "GEAP"]
INDICACOES = [
    "AVALIAÇÃO MÉDICA (CLÍNICO)",
    "DOR TORÁCICA",
    "DISPNEIA",
    "CEFALEIA",
    "CONVULSÃO",
    "CHECK-UP OCUPACIONAL",
    "PRÉ-OPERATÓRIO",
    "ACOMPANHAMENTO",
    "TOSSE PROLONGADA",
    "TRAUMA",
    "SUSPEITA DE EPILEPSIA",
    "HIPERTENSÃO ARTERIAL",
    "PALPITAÇÕES",
    "RONCO E SONOLÊNCIA",
    "ALTERAÇÃO VISUAL",
    "DOR LOMBAR",
    "DOR ARTICULAR",
    "NÓDULO MAMÁRIO",
    "RASTREAMENTO",
    "CONTROLE PÓS-TRATAMENTO",
]

EXAMES = [
    {
        "slug": "rx-torax",
        "titulo": "Laudo Radiográfico",
        "secao": "TÓRAX - PA e Perfil",
        "especialidade": "Radiologista",
        "layout": "rx",
        "indicacoes": ["AVALIAÇÃO MÉDICA (CLÍNICO)", "DOR TORÁCICA", "DISPNEIA", "TOSSE PROLONGADA", "PRÉ-OPERATÓRIO", "CHECK-UP OCUPACIONAL"],
        "variantes": [
            {
                "analise": [
                    "Estruturas ósseas sem alterações evidenciáveis.",
                    "Área cardíaca e hilos pulmonares de aspecto normal.",
                    "Mediastino anatômico.",
                    "Pulmões com transparência conservada.",
                    "Espaços pleurais livres.",
                ],
                "consideracoes": "Exame radiológico de aspecto normal.",
            },
            {
                "analise": [
                    "Índice cardiotorácico aumentado, compatível com cardiomegalia discreta.",
                    "Hilos pulmonares proeminentes.",
                    "Sinais de congestão pulmonar leve nas bases.",
                    "Seios costofrênicos livres.",
                    "Estruturas ósseas preservadas.",
                ],
                "consideracoes": "Cardiomegalia discreta associada a sinais de congestão pulmonar leve. Correlação clínica recomendada.",
            },
            {
                "analise": [
                    "Opacidade alveolar em lobo inferior direito, de contornos mal definidos.",
                    "Área cardíaca dentro dos limites da normalidade.",
                    "Mediastino centrado.",
                    "Espaço pleural direito com mínimo velamento da base.",
                    "Grade costal sem fraturas visíveis.",
                ],
                "consideracoes": "Opacidade em lobo inferior direito, podendo corresponder a processo inflamatório/infeccioso. Sugere-se correlação clínica e controle evolutivo.",
            },
            {
                "analise": [
                    "Hiperinsuflação pulmonar com retificação das cúpulas diafragmáticas.",
                    "Aumento dos espaços intercostais.",
                    "Área cardíaca alongada, de aspecto verticalizado.",
                    "Ausência de consolidação alveolar.",
                    "Seios costofrênicos livres.",
                ],
                "consideracoes": "Sinais radiológicos de hiperinsuflação pulmonar, sugestivos de doença pulmonar obstrutiva. Correlação com espirometria é aconselhável.",
            },
            {
                "analise": [
                    "Nódulo pulmonar de 1,2 cm em lobo superior esquerdo, de contornos regulares.",
                    "Parênquima restante sem consolidações.",
                    "Mediastino sem alargamento evidente.",
                    "Área cardíaca normal.",
                    "Estruturas ósseas sem lesões líticas.",
                ],
                "consideracoes": "Nódulo pulmonar isolado à esquerda. Recomenda-se tomografia de tórax para melhor caracterização.",
            },
        ],
    },
    {
        "slug": "rx-coluna-lombar",
        "titulo": "Laudo Radiográfico",
        "secao": "COLUNA LOMBAR - AP e Perfil",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Alinhamento vertebral preservado.",
                    "Alturas dos corpos vertebrais conservadas.",
                    "Espaços discais de amplitude habitual.",
                    "Ausência de listese.",
                    "Partes moles adjacentes sem alterações visíveis.",
                ],
                "consideracoes": "Estudo radiográfico da coluna lombar sem alterações significativas.",
            },
            {
                "analise": [
                    "Redução dos espaços discais L4-L5 e L5-S1.",
                    "Osteófitos anteriores em corpos vertebrais lombares.",
                    "Esclerose das platôs vertebrais.",
                    "Retificação da lordose lombar fisiológica.",
                    "Forames de conjugação de difícil avaliação neste método.",
                ],
                "consideracoes": "Sinais de espondilose lombar e discopatia degenerativa em L4-L5 e L5-S1.",
            },
            {
                "analise": [
                    "Escoliose lombar de convexidade esquerda, com ângulo de Cobb estimado em 18°.",
                    "Rotações vertebrais discretas.",
                    "Alturas vertebrais preservadas.",
                    "Ausência de lesões ósseas agudas.",
                    "Sacro e articulações sacroilíacas de aspecto habitual nesta incidência.",
                ],
                "consideracoes": "Escoliose lombar leve. Avaliação clínica e, se indicado, estudo complementar.",
            },
        ],
    },
    {
        "slug": "rx-joelho",
        "titulo": "Laudo Radiográfico",
        "secao": "JOELHO DIREITO - AP e Perfil",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Interlinha articular preservada.",
                    "Superfícies ósseas regulares, sem erosões.",
                    "Patela centrada, sem sinais de fratura.",
                    "Partes moles de volume habitual.",
                    "Ausência de corpo livre ósseo visível.",
                ],
                "consideracoes": "Radiografia de joelho direito sem alterações evidentes.",
            },
            {
                "analise": [
                    "Redução assimétrica da interlinha femorotibial medial.",
                    "Osteófitos marginais no côndilo femoral e platô tibial.",
                    "Esclerose subcondral.",
                    "Patela com osteófito no polo superior.",
                    "Sem sinais de fratura aguda.",
                ],
                "consideracoes": "Gonartrose medial moderada. Correlação clínica e, se necessário, ressonância magnética.",
            },
        ],
    },
    {
        "slug": "rx-seios-face",
        "titulo": "Laudo Radiográfico",
        "secao": "SEIOS DA FACE",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Seios maxilares, etmoidais e frontais aerados.",
                    "Paredes ósseas íntegras.",
                    "Septo nasal centrado.",
                    "Ausência de níveis hidroaéreos.",
                    "Partes moles de aspecto habitual.",
                ],
                "consideracoes": "Radiografia dos seios da face sem alterações significativas.",
            },
            {
                "analise": [
                    "Velamento do seio maxilar esquerdo.",
                    "Espessamento mucoso sugestivo.",
                    "Seio maxilar direito aerado.",
                    "Seios frontais simétricos.",
                    "Paredes ósseas sem erosão visível.",
                ],
                "consideracoes": "Sinais radiológicos compatíveis com sinusopatia maxilar à esquerda.",
            },
        ],
    },
    {
        "slug": "eeg",
        "titulo": "Laudo de Eletroencefalograma",
        "secao": "ELETROENCEFALOGRAMA",
        "especialidade": "Neurologista",
        "layout": "eeg",
        "indicacoes": ["AVALIAÇÃO MÉDICA (CLÍNICO)", "CEFALEIA", "CONVULSÃO", "SUSPEITA DE EPILEPSIA", "ACOMPANHAMENTO"],
        "variantes": [
            {
                "tecnica": "Constante de tempo de 0,3 segundos. Frequência de amostragem de 256 amostras por canal por segundo. Montagem 10-20.",
                "resultados": [
                    "Ritmo de base regular, simétrico e sincrônico para a faixa etária.",
                    "Exame realizado em vigília, com boa colaboração.",
                    "Fotoestimulação sem evidência de paroxismos.",
                    "Hiperventilação sem alteração adicional.",
                    "Registro com artefatos musculares esparsos, sem prejuízo diagnóstico relevante.",
                ],
                "conclusao": "Eletroencefalograma dentro dos limites da normalidade.",
            },
            {
                "tecnica": "Constante de tempo de 0,3 segundos. Frequência de amostragem de 256 amostras por canal por segundo.",
                "resultados": [
                    "Ritmo de base irregular, assimétrico, assíncrono e complexo.",
                    "Exame realizado em vigília.",
                    "Fotoestimulação não acrescentou novos achados.",
                    "Raros paroxismos lentos em regiões temporais, sem predomínio hemisférico nítido.",
                    "Registro com numerosos artefatos.",
                ],
                "conclusao": "Discretos sinais de disfunção cortical de caráter inespecífico.",
            },
            {
                "tecnica": "Sistema 10-20, filtros padronizados, registro em vigília e sonolência.",
                "resultados": [
                    "Atividade de base desorganizada para a idade.",
                    "Descargas epileptiformes ponta-onda a 3 Hz, generalizadas, de breve duração.",
                    "Fotoestimulação intermitente precipitou paroxismos semelhantes.",
                    "Sem assimetria persistente de voltagem.",
                    "Artefatos de movimento pontuais.",
                ],
                "conclusao": "Traçado com atividade epileptiforme generalizada, compatível com padrão de ausência. Correlação clínica obrigatória.",
            },
            {
                "tecnica": "Registro de 30 minutos, com prova de fotoestimulação e hiperventilação.",
                "resultados": [
                    "Ritmo alfa occipital reativo à abertura ocular.",
                    "Focos de pontas e ondas agudas em temporal esquerdo.",
                    "Sem generalização secundária durante o registro.",
                    "Hiperventilação acentuou a atividade lenta temporal.",
                    "Sono não obtido neste exame.",
                ],
                "conclusao": "Atividade epileptiforme focal em região temporal esquerda. Sugere-se correlação com história clínica e, se indicado, EEG prolongado.",
            },
        ],
    },
    {
        "slug": "ecg",
        "titulo": "Laudo de Eletrocardiograma",
        "secao": "ELETROCARDIOGRAMA DE REPOUSO (12 DERIVAÇÕES)",
        "especialidade": "Cardiologista",
        "layout": "cardio",
        "variantes": [
            {
                "analise": [
                    "Ritmo sinusal. Frequência cardíaca de 68 bpm.",
                    "Eixo elétrico normal.",
                    "Intervalo PR de 160 ms. QRS de 88 ms. QTc de 410 ms.",
                    "Sem alterações do segmento ST ou da onda T.",
                    "Sem sinais de sobrecarga atrial ou ventricular.",
                ],
                "consideracoes": "Eletrocardiograma de repouso normal.",
            },
            {
                "analise": [
                    "Ritmo sinusal. Frequência cardíaca de 92 bpm.",
                    "Sobrecarga ventricular esquerda (Sokolow-Lyon positivo).",
                    "Alterações inespecíficas da repolarização ventricular em precordiais esquerdas.",
                    "Intervalos de condução dentro da normalidade.",
                    "Sem bloqueios atrioventriculares.",
                ],
                "consideracoes": "Sobrecarga ventricular esquerda com alterações inespecíficas da repolarização. Correlação com hipertensão arterial e ecocardiograma, se clinicamente indicado.",
            },
            {
                "analise": [
                    "Fibrilação atrial de resposta ventricular controlada (FC média 84 bpm).",
                    "Ausência de ondas P. Intervalos RR irregulares.",
                    "QRS estreito.",
                    "Alterações difusas e inespecíficas da repolarização.",
                    "Sem supradesnivelamento de ST.",
                ],
                "consideracoes": "Fibrilação atrial com resposta ventricular controlada. Avaliação clínica e de risco tromboembólico recomendada.",
            },
            {
                "analise": [
                    "Ritmo sinusal. Frequência de 56 bpm.",
                    "Bloqueio de ramo direito completo.",
                    "Eixo desviado à direita.",
                    "Sem alterações isquêmicas agudas.",
                    "QTc nos limites da normalidade.",
                ],
                "consideracoes": "Bloqueio de ramo direito completo, sem sinais eletrocardiográficos de isquemia aguda.",
            },
        ],
    },
    {
        "slug": "holter",
        "titulo": "Laudo de Holter 24 horas",
        "secao": "HOLTER 24 HORAS",
        "especialidade": "Cardiologista",
        "layout": "cardio",
        "variantes": [
            {
                "analise": [
                    "Ritmo de base sinusal durante todo o período.",
                    "FC mínima 52 bpm, média 71 bpm, máxima 128 bpm.",
                    "Extrasístoles ventriculares isoladas raras (<1%).",
                    "Ausência de taquicardia ventricular sustentada.",
                    "Sem pausas significativas (>2,0 s).",
                ],
                "consideracoes": "Holter 24 horas sem arritmias clinicamente relevantes.",
            },
            {
                "analise": [
                    "Ritmo sinusal predominante.",
                    "Salvas de taquicardia atrial não sustentada (maior salva com 8 batimentos).",
                    "Carga de extrasístoles supraventriculares de 4,8%.",
                    "FC máxima 146 bpm relacionada a esforço.",
                    "Sem bloqueio atrioventricular avançado.",
                ],
                "consideracoes": "Ectopia supraventricular frequente com taquicardia atrial não sustentada. Correlação com sintomas e avaliação cardiológica.",
            },
        ],
    },
    {
        "slug": "mapa",
        "titulo": "Laudo de MAPA",
        "secao": "MONITORIZAÇÃO AMBULATORIAL DA PRESSÃO ARTERIAL (24 HORAS)",
        "especialidade": "Cardiologista",
        "layout": "cardio",
        "variantes": [
            {
                "analise": [
                    "PA média 24 h: 118 x 74 mmHg.",
                    "PA vigília: 124 x 78 mmHg. PA sono: 106 x 64 mmHg.",
                    "Descenso noturno sistólico de 14% (padrão dipper).",
                    "Carga pressórica dentro da normalidade.",
                    "Boa qualidade técnica do registro (85% de medidas válidas).",
                ],
                "consideracoes": "MAPA dentro dos limites da normalidade, com descenso noturno preservado.",
            },
            {
                "analise": [
                    "PA média 24 h: 142 x 91 mmHg.",
                    "PA vigília: 148 x 94 mmHg. PA sono: 138 x 88 mmHg.",
                    "Descenso noturno atenuado (não dipper).",
                    "Carga pressórica elevada, sobretudo no período de sono.",
                    "Sintomas de cefaleia referidos no diário coincidem com picos pressóricos.",
                ],
                "consideracoes": "Hipertensão arterial ao MAPA, com padrão não dipper. Ajuste terapêutico e seguimento clínico indicados.",
            },
        ],
    },
    {
        "slug": "teste-ergometrico",
        "titulo": "Laudo de Teste Ergométrico",
        "secao": "TESTE ERGOMÉTRICO (PROTOCOLO DE BRUCE)",
        "especialidade": "Cardiologista",
        "layout": "cardio",
        "variantes": [
            {
                "analise": [
                    "Capacidade funcional de 11,2 METs, adequada para a idade.",
                    "Resposta cronotrópica e pressórica fisiológicas.",
                    "Sem infradesnivelamento significativo de ST.",
                    "Sem arritmias complexas ao esforço.",
                    "Recuperação da FC adequada no primeiro minuto.",
                ],
                "consideracoes": "Teste ergométrico máximo, clinicamente e eletrocardiograficamente negativo para isquemia.",
            },
            {
                "analise": [
                    "Interrompido por cansaço e desconforto precordial aos 7,4 METs.",
                    "Infradesnivelamento de ST de 1,8 mm em DII, DIII, aVF e V4-V6.",
                    "Resposta pressórica exagerada (PA pico 210 x 102 mmHg).",
                    "Extrasístoles ventriculares isoladas no pico do esforço.",
                    "Recuperação lenta do segmento ST.",
                ],
                "consideracoes": "Teste ergométrico positivo para isquemia miocárdica. Avaliação cardiológica complementar é recomendada.",
            },
        ],
    },
    {
        "slug": "espirometria",
        "titulo": "Laudo de Espirometria",
        "secao": "ESPIROMETRIA COM CURVA FLUXO-VOLUME",
        "especialidade": "Pneumologista",
        "layout": "pulmao",
        "variantes": [
            {
                "analise": [
                    "CVF 102% do previsto. VEF1 98% do previsto. Relação VEF1/CVF 0,81.",
                    "Curva fluxo-volume de morfologia habitual.",
                    "Resposta ao broncodilatador não significativa.",
                    "Exame tecnicamente aceitável e reprodutível.",
                    "Sem sinais de restrição ou obstrução.",
                ],
                "consideracoes": "Prova de função pulmonar dentro dos limites da normalidade.",
            },
            {
                "analise": [
                    "VEF1 62% do previsto. Relação VEF1/CVF 0,62.",
                    "CVF 84% do previsto.",
                    "Concavidade na alça expiratória da curva fluxo-volume.",
                    "Variação do VEF1 após broncodilatador de +9% (não criteriosa).",
                    "Padrão obstrutivo moderado.",
                ],
                "consideracoes": "Distúrbio ventilatório obstrutivo moderado, sem resposta broncodilatadora significativa neste exame.",
            },
            {
                "analise": [
                    "CVF 68% do previsto. VEF1 72% do previsto. Relação VEF1/CVF 0,84.",
                    "CPT não disponível neste exame simples.",
                    "Curva com volumes reduzidos e fluxos relativamente preservados.",
                    "Sem resposta ao broncodilatador.",
                    "Padrão sugestivo de restrição, a confirmar com pletismografia se indicado.",
                ],
                "consideracoes": "Distúrbio ventilatório restritivo sugestivo. Correlação clínica e radiológica recomendada.",
            },
        ],
    },
    {
        "slug": "mamografia",
        "titulo": "Laudo de Mamografia",
        "secao": "MAMOGRAFIA DIGITAL BILATERAL",
        "especialidade": "Radiologista",
        "layout": "rx",
        "sexo": "F",
        "idade_min": 35,
        "variantes": [
            {
                "analise": [
                    "Mamas de padrão fibroglandular esparso (tipo B).",
                    "Ausência de nódulos, microcalcificações suspeitas ou distorção arquitetural.",
                    "Pele e complexos aréolo-papilares sem alterações.",
                    "Axilas sem linfonodomegalias evidentes nas incidências realizadas.",
                    "Comparação com exames anteriores não disponível.",
                ],
                "consideracoes": "BI-RADS 1 — mamografia negativa. Controle habitual conforme rastreamento.",
            },
            {
                "analise": [
                    "Mamas densas (tipo C), o que reduz a sensibilidade do método.",
                    "Nódulo oval, circunscrito, de 0,9 cm em quadrante superolateral esquerdo.",
                    "Sem microcalcificações pleomórficas.",
                    "Linfonodos axilares de aspecto habitual.",
                    "Pele sem espessamento.",
                ],
                "consideracoes": "BI-RADS 3 — achado provavelmente benigno. Controle em 6 meses ou ultrassonografia complementar.",
            },
            {
                "analise": [
                    "Nódulo irregular, de margens espiculadas, 1,4 cm, união dos quadrantes superiores à direita.",
                    "Microcalcificações pleomórficas agrupadas adjacentes à lesão.",
                    "Retração discreta da pele sobrejacente.",
                    "Linfonodo axilar direito de cortical espessada.",
                    "Mama esquerda sem lesões suspeitas neste exame.",
                ],
                "consideracoes": "BI-RADS 5 — altamente sugestivo de malignidade. Biópsia e avaliação multidisciplinar indicadas.",
            },
        ],
    },
    {
        "slug": "tc-cranio",
        "titulo": "Laudo de Tomografia Computadorizada",
        "secao": "TOMOGRAFIA DE CRÂNIO SEM CONTRASTE",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Parênquima encefálico com densidade preservada, sem coleções.",
                    "Sistema ventricular de dimensões habituais, centrado.",
                    "Cisternas da base pérvias.",
                    "Ausência de hemorragia intracraniana visível.",
                    "Estruturas ósseas do calvário sem fraturas evidentes nas janelas ósseas.",
                ],
                "consideracoes": "Tomografia de crânio sem alterações agudas evidenciáveis.",
            },
            {
                "analise": [
                    "Área hipodensa corticossubcortical em território de ACM esquerda, sem efeito de massa significativo.",
                    "Apagamento de sulcos adjacentes.",
                    "Não há hiperdensidade da ACM neste exame.",
                    "Linha média centrada.",
                    "Seios da face com velamento etmoidal discreto, incidental.",
                ],
                "consideracoes": "Achados compatíveis com acidente vascular encefálico isquêmico em evolução à esquerda. Correlação clínica e tempo de início dos sintomas são essenciais.",
            },
            {
                "analise": [
                    "Hematoma subdural crônico à direita, com espessura máxima de 11 mm.",
                    "Desvio da linha média de 3 mm.",
                    "Sem sinais de herniação.",
                    "Parênquima sem lesão intra-axial aguda adicional.",
                    "Calota craniana íntegra.",
                ],
                "consideracoes": "Hematoma subdural crônico à direita com mínimo efeito de massa. Avaliação neurocirúrgica conforme status clínico.",
            },
        ],
    },
    {
        "slug": "tc-torax",
        "titulo": "Laudo de Tomografia Computadorizada",
        "secao": "TOMOGRAFIA DE TÓRAX SEM CONTRASTE",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Parênquima pulmonar sem nódulos, consolidações ou vidro fosco.",
                    "Vias aéreas pérvias, sem bronquiectasias.",
                    "Mediastino sem linfonodomegalias.",
                    "Área cardíaca e grandes vasos de calibre habitual.",
                    "Espaços pleurais livres. Sem derrame pericárdico.",
                ],
                "consideracoes": "Tomografia de tórax sem achados significativos.",
            },
            {
                "analise": [
                    "Opacidades em vidro fosco esparsas, predominantes em bases, de distribuição periférica.",
                    "Espessamento septal discreto.",
                    "Ausência de cavitações.",
                    "Linfonodos mediastinais de dimensões limítrofes.",
                    "Sem trombo visível neste protocolo sem contraste.",
                ],
                "consideracoes": "Opacidades em vidro fosco de padrão inflamatório/infeccioso. Correlação clínica, laboratorial e evolutiva.",
            },
        ],
    },
    {
        "slug": "rm-joelho",
        "titulo": "Laudo de Ressonância Magnética",
        "secao": "RESSONÂNCIA MAGNÉTICA DO JOELHO ESQUERDO",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Ligamentos cruzados anterior e posterior íntegros, com sinal habitual.",
                    "Meniscos medial e lateral sem sinais de ruptura.",
                    "Cartilagem articular preservada.",
                    "Ausência de derrame articular significativo.",
                    "Tendão patelar e quadricipital sem tendinopatia relevante.",
                ],
                "consideracoes": "Ressonância magnética do joelho esquerdo sem alterações significativas.",
            },
            {
                "analise": [
                    "Ruptura completa do ligamento cruzado anterior, com descontinuidade de fibras.",
                    "Edema ósseo no côndilo femoral lateral e platô tibial posterior (contusão óssea).",
                    "Ruptura longitudinal do corno posterior do menisco medial.",
                    "Derrame articular moderado.",
                    "Ligamento cruzado posterior íntegro.",
                ],
                "consideracoes": "Ruptura completa do LCA associada a lesão meniscal medial e contusão óssea. Correlação ortopédica.",
            },
        ],
    },
    {
        "slug": "rm-coluna",
        "titulo": "Laudo de Ressonância Magnética",
        "secao": "RESSONÂNCIA MAGNÉTICA DA COLUNA LOMBAR",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Alinhamento vertebral preservado.",
                    "Discos com sinal e altura preservados.",
                    "Canal vertebral de calibre habitual.",
                    "Cone medular e cauda equina sem compressões.",
                    "Sem listese. Articulações facetárias sem artrose relevante.",
                ],
                "consideracoes": "RM da coluna lombar sem alterações compressivas ou degenerativas significativas.",
            },
            {
                "analise": [
                    "Protrusão discal centro-lateral esquerda em L4-L5, contactando a raiz emergente.",
                    "Redução de sinal discal em L4-L5 e L5-S1 (desidratação).",
                    "Canal vertebral com estenose relativa em L4-L5.",
                    "Artrose facetária bilateral discreta.",
                    "Cono medular de topografia e sinal habituais.",
                ],
                "consideracoes": "Doença discal degenerativa com protrusão em L4-L5 e contato radicular à esquerda. Correlação com o quadro álgico.",
            },
        ],
    },
    {
        "slug": "densitometria",
        "titulo": "Laudo de Densitometria Óssea",
        "secao": "DENSITOMETRIA ÓSSEA (DXA) - COLUNA E FÊMUR",
        "especialidade": "Radiologista",
        "layout": "rx",
        "idade_min": 40,
        "variantes": [
            {
                "analise": [
                    "Coluna lombar (L1-L4): T-score -0,8.",
                    "Colo femoral: T-score -0,6.",
                    "Fêmur total: T-score -0,5.",
                    "Exame tecnicamente adequado, sem artefatos metálicos.",
                    "Comparação anterior indisponível.",
                ],
                "consideracoes": "Densidade mineral óssea dentro da faixa de normalidade (OMS).",
            },
            {
                "analise": [
                    "Coluna lombar (L1-L4): T-score -2,1.",
                    "Colo femoral: T-score -1,8.",
                    "Fêmur total: T-score -1,7.",
                    "Sem fraturas vertebrais evidentes nesta aquisição.",
                    "IMC 24,1 kg/m² informado no pedido.",
                ],
                "consideracoes": "Osteopenia. Recomenda-se correlação com fatores de risco e conduta clínica para prevenção de fraturas.",
            },
            {
                "analise": [
                    "Coluna lombar (L1-L4): T-score -3,2.",
                    "Colo femoral: T-score -2,9.",
                    "Fêmur total: T-score -2,7.",
                    "Z-score não aplicável como critério diagnóstico nesta faixa etária pós-menopausa.",
                    "Qualidade técnica satisfatória.",
                ],
                "consideracoes": "Osteoporose densitométrica. Avaliação clínica, laboratorial e de risco de fratura indicada.",
            },
        ],
    },
    {
        "slug": "us-abdome",
        "titulo": "Laudo de Ultrassonografia",
        "secao": "ULTRASSONOGRAFIA DE ABDÔMEN TOTAL",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Fígado de dimensões e ecogenicidade habituais, sem lesões focais.",
                    "Vesícula biliar alitiásica, paredes finas.",
                    "Pâncreas e baço sem alterações visíveis.",
                    "Rins tópicos, com diferenciação corticomedular preservada, sem hidronefrose.",
                    "Aorta abdominal de calibre habitual. Ausência de líquido livre.",
                ],
                "consideracoes": "Ultrassonografia de abdome total sem alterações significativas.",
            },
            {
                "analise": [
                    "Fígado com aumento da ecogenicidade, sugestivo de esteatose moderada.",
                    "Múltiplos cálculos em vesícula biliar, o maior de 12 mm, sem sinais de colecistite aguda.",
                    "Vias biliares intra e extra-hepáticas de calibre normal.",
                    "Rins sem cálculos visíveis neste método.",
                    "Baço de dimensões conservadas.",
                ],
                "consideracoes": "Esteatose hepática moderada e colelitíase. Sem sinais de colecistite aguda neste exame.",
            },
        ],
    },
    {
        "slug": "us-tireoide",
        "titulo": "Laudo de Ultrassonografia",
        "secao": "ULTRASSONOGRAFIA DE TIREOIDE",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Tireoide de dimensões habituais, parênquima homogêneo.",
                    "Ausência de nódulos.",
                    "Istmo fino.",
                    "Vasos cervicais de trajeto habitual.",
                    "Cadeias linfonodais cervicais sem adenomegalias.",
                ],
                "consideracoes": "Ultrassonografia de tireoide sem alterações.",
            },
            {
                "analise": [
                    "Nódulo sólido, hipoecoico, 1,1 cm, no terço médio do lobo direito, margens regulares, sem microcalcificações.",
                    "Fluxo periférico ao Doppler.",
                    "Lobo esquerdo homogêneo.",
                    "Sem linfonodos suspeitos.",
                    "Volume glandular total de 11,4 cm³.",
                ],
                "consideracoes": "Nódulo tireoidiano ACR TI-RADS 3. Seguimento ultrassonográfico conforme protocolo institucional.",
            },
        ],
    },
    {
        "slug": "polissonografia",
        "titulo": "Laudo de Polissonografia",
        "secao": "POLISSONOGRAFIA DE NOITE INTEIRA TIPO I",
        "especialidade": "Neurologista",
        "layout": "eeg",
        "idade_min": 16,
        "variantes": [
            {
                "tecnica": "Registro em laboratório do sono, com EEG, EOG, EMG, fluxo aéreo, esforço toracoabdominal, SpO2 e ECG.",
                "resultados": [
                    "Eficiência do sono de 88%. Latência do sono de 14 minutos.",
                    "Arquitetura do sono preservada, com representação adequada de N3 e REM.",
                    "Índice de apneia-hipopneia (IAH) de 3,1 eventos/hora.",
                    "SpO2 mínima de 91%. Tempo com SpO2 <90% inferior a 1%.",
                    "Índice de movimentos periódicos de pernas dentro da normalidade.",
                ],
                "conclusao": "Polissonografia sem evidência de apneia obstrutiva do sono clinicamente significativa.",
            },
            {
                "tecnica": "Polissonografia basal em laboratório, sem CPAP nesta noite.",
                "resultados": [
                    "Eficiência do sono de 72%. Fragmentação importante.",
                    "IAH de 28,4 eventos/hora, predominância obstrutiva, pior em sono REM e decúbito dorsal.",
                    "SpO2 mínima de 78%. Tempo com dessaturação relevante elevado.",
                    "Ronco persistente. Microdesperts associados aos eventos respiratórios.",
                    "ECG sem arritmias graves no registro.",
                ],
                "conclusao": "Síndrome da apneia obstrutiva do sono de grau moderado a grave. Avaliação para terapia ventilatória e medidas gerais.",
            },
        ],
    },
    {
        "slug": "fundoscopia",
        "titulo": "Laudo de Fundoscopia",
        "secao": "FUNDOSCOPIA BINOCULAR INDIRETA",
        "especialidade": "Oftalmologista",
        "layout": "oftalmo",
        "variantes": [
            {
                "analise": [
                    "Papilas ópticas de coloração e escavação habituais (relação 0,3).",
                    "Máculas sem edema ou exsudatos.",
                    "Vasos de trajeto e calibre preservados.",
                    "Retina aplicada nos 360°, sem roturas visíveis.",
                    "Meios relativamente transparentes.",
                ],
                "consideracoes": "Fundoscopia sem alterações significativas em ambos os olhos.",
            },
            {
                "analise": [
                    "Estreitamento arteriolar difuso e cruzamentos arteriovenosos patológicos.",
                    "Microaneurismas e hemorragias em chama de vela no polo posterior do olho direito.",
                    "Ausência de neovasos neste exame.",
                    "Papilas sem edema.",
                    "Olho esquerdo com alterações hipertensivas leves, sem hemorragias.",
                ],
                "consideracoes": "Retinopatia hipertensiva moderada à direita e leve à esquerda. Controle pressórico e reavaliação oftalmológica.",
            },
        ],
    },
    {
        "slug": "campimetria",
        "titulo": "Laudo de Campimetria",
        "secao": "CAMPIMETRIA COMPUTADORIZADA (24-2)",
        "especialidade": "Oftalmologista",
        "layout": "oftalmo",
        "variantes": [
            {
                "analise": [
                    "Confiabilidade boa (falsos positivos e negativos <15%).",
                    "MD e PSD dentro da normalidade em ambos os olhos.",
                    "Ausência de defeitos glaucomatosos típicos.",
                    "Ponto cego fisiológico localizado.",
                    "Campos visuais simétricos.",
                ],
                "consideracoes": "Campimetria computadorizada dentro dos limites da normalidade.",
            },
            {
                "analise": [
                    "Confiabilidade aceitável.",
                    "Defeito arqueado superior no olho direito, compatível com padrão glaucomatoso.",
                    "MD reduzido no olho direito. Olho esquerdo limítrofe.",
                    "Fixação central preservada.",
                    "Sugestivo de dano funcional assimétrico.",
                ],
                "consideracoes": "Alteração campimétrica sugestiva de glaucoma no olho direito. Correlação com PIO, papila e RNFL.",
            },
        ],
    },
    {
        "slug": "acuidade-visual",
        "titulo": "Laudo de Acuidade Visual",
        "secao": "AVALIAÇÃO DE ACUIDADE VISUAL E REFRAÇÃO",
        "especialidade": "Oftalmologista",
        "layout": "oftalmo",
        "variantes": [
            {
                "analise": [
                    "AV com correção: 20/20 em ambos os olhos.",
                    "Refração: OD -0,50 esf. OE -0,75 esf. -0,25 cil a 180°.",
                    "Motilidade extrínseca preservada. Cover test sem desvio.",
                    "Pressão intraocular: 14 mmHg OD e 15 mmHg OE (ar).",
                    "Segmento anterior sem alterações à lâmpada de fenda.",
                ],
                "consideracoes": "Exame oftalmológico funcional dentro da normalidade, com ametropia leve.",
            },
            {
                "analise": [
                    "AV sem correção: 20/60 OD e 20/40 OE.",
                    "AV com correção: 20/25 OD e 20/20 OE.",
                    "Miopia e astigmatismo compostos.",
                    "Sem sinais de ambliopia nesta avaliação.",
                    "Fundoscopia sumária sem lesões maculares.",
                ],
                "consideracoes": "Baixa visual corrigível por erro refracional. Prescrição óptica atualizada recomendada.",
            },
        ],
    },
    {
        "slug": "itb",
        "titulo": "Laudo de Índice Tornozelo-Braço",
        "secao": "ÍNDICE TORNOZELO-BRAÇO (ITB)",
        "especialidade": "Cardiologista",
        "layout": "cardio",
        "idade_min": 30,
        "variantes": [
            {
                "analise": [
                    "PAS braquial direita 128 mmHg; esquerda 126 mmHg.",
                    "PAS tibial posterior direita 124 mmHg; esquerda 122 mmHg.",
                    "ITB direito 0,97. ITB esquerdo 0,97.",
                    "Curvas Doppler trifásicas em artérias pediosas.",
                    "Exame tecnicamente adequado.",
                ],
                "consideracoes": "ITB dentro da normalidade, sem evidência de doença arterial periférica obstrutiva neste método.",
            },
            {
                "analise": [
                    "PAS braquial 138 mmHg.",
                    "PAS tibial posterior direita 86 mmHg; esquerda 118 mmHg.",
                    "ITB direito 0,62. ITB esquerdo 0,86.",
                    "Curva Doppler monofásica à direita.",
                    "Paciente refere claudicação em panturrilha direita aos 200 m.",
                ],
                "consideracoes": "ITB reduzido à direita, compatível com doença arterial periférica moderada. Avaliação vascular recomendada.",
            },
        ],
    },
    {
        "slug": "angio-tc",
        "titulo": "Laudo de Angiotomografia",
        "secao": "ANGIOTOMOGRAFIA DE TÓRAX (TEP)",
        "especialidade": "Radiologista",
        "layout": "rx",
        "variantes": [
            {
                "analise": [
                    "Adequada opacificação das artérias pulmonares principais, lobares e segmentares.",
                    "Ausência de falhas de enchimento compatíveis com tromboembolismo.",
                    "Relação VD/VE preservada. Septo interventricular sem desvio.",
                    "Parênquima sem infartos pulmonares visíveis.",
                    "Sem derrame pleural relevante.",
                ],
                "consideracoes": "Angiotomografia negativa para tromboembolismo pulmonar agudo.",
            },
            {
                "analise": [
                    "Falhas de enchimento em artérias segmentares dos lobos inferiores, bilaterais.",
                    "Artéria pulmonar principal de calibre limítrofe.",
                    "Relação VD/VE discretamente aumentada.",
                    "Pequenas opacidades periféricas de base pleural à direita, possíveis infartos.",
                    "Sem aneurisma de aorta neste campo de visão.",
                ],
                "consideracoes": "Tromboembolismo pulmonar agudo segmentar bilateral, com sinais discretos de repercussão no ventrículo direito.",
            },
        ],
    },
]


EXAM_HINTS = {
    "rx-coluna-lombar": {"idade_min": 12, "indicacoes": ["DOR LOMBAR", "TRAUMA", "AVALIAÇÃO MÉDICA (CLÍNICO)", "ACOMPANHAMENTO"]},
    "rx-joelho": {"idade_min": 8, "indicacoes": ["DOR ARTICULAR", "TRAUMA", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "rx-seios-face": {"indicacoes": ["CEFALEIA", "AVALIAÇÃO MÉDICA (CLÍNICO)", "TOSSE PROLONGADA"]},
    "ecg": {"idade_min": 12, "indicacoes": ["DOR TORÁCICA", "PALPITAÇÕES", "PRÉ-OPERATÓRIO", "CHECK-UP OCUPACIONAL", "HIPERTENSÃO ARTERIAL"]},
    "holter": {"idade_min": 16, "indicacoes": ["PALPITAÇÕES", "AVALIAÇÃO MÉDICA (CLÍNICO)", "ACOMPANHAMENTO"]},
    "mapa": {"idade_min": 18, "indicacoes": ["HIPERTENSÃO ARTERIAL", "CHECK-UP OCUPACIONAL", "ACOMPANHAMENTO"]},
    "teste-ergometrico": {"idade_min": 18, "indicacoes": ["DOR TORÁCICA", "DISPNEIA", "CHECK-UP OCUPACIONAL", "PRÉ-OPERATÓRIO"]},
    "espirometria": {"idade_min": 8, "indicacoes": ["DISPNEIA", "TOSSE PROLONGADA", "CHECK-UP OCUPACIONAL"]},
    "mamografia": {"indicacoes": ["RASTREAMENTO", "NÓDULO MAMÁRIO", "ACOMPANHAMENTO", "CONTROLE PÓS-TRATAMENTO"]},
    "tc-cranio": {"indicacoes": ["CEFALEIA", "TRAUMA", "CONVULSÃO", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "tc-torax": {"indicacoes": ["DISPNEIA", "TOSSE PROLONGADA", "DOR TORÁCICA", "CONTROLE PÓS-TRATAMENTO"]},
    "rm-joelho": {"idade_min": 12, "indicacoes": ["DOR ARTICULAR", "TRAUMA", "ACOMPANHAMENTO"]},
    "rm-coluna": {"idade_min": 16, "indicacoes": ["DOR LOMBAR", "AVALIAÇÃO MÉDICA (CLÍNICO)", "ACOMPANHAMENTO"]},
    "densitometria": {"indicacoes": ["RASTREAMENTO", "ACOMPANHAMENTO", "CHECK-UP OCUPACIONAL"]},
    "us-abdome": {"indicacoes": ["AVALIAÇÃO MÉDICA (CLÍNICO)", "DOR ARTICULAR", "ACOMPANHAMENTO"]},
    "us-tireoide": {"indicacoes": ["AVALIAÇÃO MÉDICA (CLÍNICO)", "ACOMPANHAMENTO", "RASTREAMENTO"]},
    "polissonografia": {"indicacoes": ["RONCO E SONOLÊNCIA", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "fundoscopia": {"indicacoes": ["ALTERAÇÃO VISUAL", "HIPERTENSÃO ARTERIAL", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "campimetria": {"idade_min": 12, "indicacoes": ["ALTERAÇÃO VISUAL", "ACOMPANHAMENTO", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "acuidade-visual": {"indicacoes": ["ALTERAÇÃO VISUAL", "CHECK-UP OCUPACIONAL", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
    "itb": {"indicacoes": ["CHECK-UP OCUPACIONAL", "AVALIAÇÃO MÉDICA (CLÍNICO)", "DOR ARTICULAR"]},
    "angio-tc": {"idade_min": 18, "indicacoes": ["DOR TORÁCICA", "DISPNEIA", "AVALIAÇÃO MÉDICA (CLÍNICO)"]},
}

for _exam in EXAMES:
    for _key, _value in EXAM_HINTS.get(_exam["slug"], {}).items():
        _exam.setdefault(_key, _value)


def _age(born: date, on: date) -> tuple[int, int]:
    years = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
    months = on.month - born.month - (on.day < born.day)
    if months < 0:
        months += 12
    return years, months


def _token(rng: random.Random, n: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(n))


def _wrap(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def _draw_fake_qr(c: canvas.Canvas, x: float, y: float, size: float, rng: random.Random) -> None:
    c.setStrokeColor(black)
    c.setFillColor(black)
    c.rect(x, y, size, size, stroke=1, fill=0)
    cells = 11
    cell = size / (cells + 2)
    for i in range(cells):
        for j in range(cells):
            if rng.random() > 0.48 or (i < 3 and j < 3) or (i < 3 and j > cells - 4) or (i > cells - 4 and j < 3):
                c.rect(x + cell * (j + 1), y + cell * (i + 1), cell * 0.9, cell * 0.9, stroke=0, fill=1)
    c.setFillColor(white)
    for ox, oy in ((1, 1), (1, cells - 2), (cells - 2, 1)):
        c.rect(x + cell * ox, y + cell * oy, cell * 2.2, cell * 2.2, stroke=0, fill=1)
    c.setFillColor(black)
    for ox, oy in ((1.4, 1.4), (1.4, cells - 1.6), (cells - 1.6, 1.4)):
        c.rect(x + cell * ox, y + cell * oy, cell * 1.3, cell * 1.3, stroke=0, fill=1)


def _draw_seal(c: canvas.Canvas, x: float, y: float, r: float) -> None:
    c.saveState()
    c.setStrokeColor(GREEN)
    c.setLineWidth(2)
    c.circle(x, y, r, stroke=1, fill=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.circle(x, y, r - 4, stroke=1, fill=0)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 6)
    c.drawCentredString(x, y + 6, "ASSINADO")
    c.drawCentredString(x, y - 2, "ELETRONICAMENTE")
    c.setFont("Helvetica", 5.5)
    c.drawCentredString(x, y - 12, "ICP-BRASIL")
    c.restoreState()


def build_record(rng: random.Random, index: int) -> dict:
    exam = EXAMES[index % len(EXAMES)]
    variant = exam["variantes"][rng.randrange(len(exam["variantes"]))]
    sexo_fixo = exam.get("sexo")
    sexo = sexo_fixo if sexo_fixo else rng.choice(["M", "F"])
    idade_min = exam.get("idade_min", 2)
    idade_max = exam.get("idade_max", 88)
    exam_date = date(2022, 1, 1) + timedelta(days=rng.randint(0, 1400))
    age_years = rng.randint(idade_min, idade_max)
    born = date(exam_date.year - age_years, rng.randint(1, 12), rng.randint(1, 28))
    years, months = _age(born, exam_date)
    first_pool = NOMES_M if sexo == "M" else NOMES_F
    nome = f"{rng.choice(first_pool)} {rng.choice(SOBRENOMES_EXTRA)}"
    medicos_esp = [m for m in MEDICOS if m[2] == exam["especialidade"]]
    medico = rng.choice(medicos_esp or MEDICOS)
    cidade, uf = rng.choice(CIDADES)
    crm = f"{rng.randint(12000, 98999)}"
    rqe = f"{rng.randint(1000, 25000)}"
    controle = f"{exam_date.year}{exam_date.month:02d}/{index:03d}"
    indicacao = rng.choice(exam.get("indicacoes") or INDICACOES)
    convenio = rng.choice(CONVENIOS)
    hora = datetime(exam_date.year, exam_date.month, exam_date.day, rng.randint(7, 18), rng.randint(0, 59))
    return {
        "index": index,
        "exam": exam,
        "variant": variant,
        "sexo": "MASCULINO" if sexo == "M" else "FEMININO",
        "nome": nome.upper(),
        "nascimento": born,
        "idade": f"{years} a. {months} m.",
        "exame_em": exam_date,
        "hora": hora,
        "indicacao": indicacao,
        "convenio": convenio,
        "medico": medico,
        "cidade": cidade,
        "uf": uf,
        "crm": crm,
        "rqe": rqe,
        "controle": controle,
        "token": _token(rng, 10),
        "validador": "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(5)),
        "endereco": f"Rua {rng.choice(SOBRENOMES_EXTRA)} {rng.randint(40, 1800)}, Centro, {cidade}-{uf}",
        "telefone": f"({rng.randint(11, 85):02d}) 3{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
    }


def render_pdf(path: Path, rec: dict, rng: random.Random) -> None:
    w, h = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(rec["exam"]["titulo"])
    c.setAuthor("Documento sintético para fins educacionais")

    margin = 16 * mm
    top = h - 12 * mm

    c.setStrokeColor(HexColor("#333333"))
    c.setLineWidth(1)
    c.rect(margin, top - 22 * mm, 32 * mm, 18 * mm, stroke=1, fill=0)
    c.setFont("Helvetica", 8)
    c.setFillColor(GRAY)
    c.drawCentredString(margin + 16 * mm, top - 13 * mm, "Logo marca")

    c.setFillColor(black)
    c.setFont("Helvetica", 8)
    c.drawCentredString(w / 2, top - 6 * mm, rec["endereco"])
    c.drawCentredString(w / 2, top - 11 * mm, f"Telefones de contato com DDD: {rec['telefone']}")

    qr_size = 18 * mm
    _draw_fake_qr(c, w - margin - qr_size, top - 20 * mm, qr_size, rng)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(w - margin, top - 23 * mm, f"Código validador: {rec['validador']}")

    title_y = top - 32 * mm
    c.setFillColor(BLUE)
    c.rect(margin, title_y - 2 * mm, w - 2 * margin, 9 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w / 2, title_y + 1 * mm, rec["exam"]["titulo"])
    c.setFillColor(black)
    c.setFont("Helvetica", 8)
    c.drawRightString(w - margin, title_y - 7 * mm, f"Controle: {rec['controle']}")

    info_y = title_y - 14 * mm
    left_x = margin
    right_x = w / 2 + 4 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x, info_y, "Nome:")
    c.drawString(left_x, info_y - 5 * mm, "Data de nascimento:")
    c.drawString(left_x, info_y - 10 * mm, "Sexo:")
    c.drawString(right_x, info_y, "Indicação:")
    c.drawString(right_x, info_y - 5 * mm, "Data do exame:")
    c.drawString(right_x, info_y - 10 * mm, "Convênio:")
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 38 * mm, info_y, rec["nome"])
    c.drawString(left_x + 38 * mm, info_y - 5 * mm, f"{rec['nascimento'].strftime('%d/%m/%Y')} ({rec['idade']})")
    c.drawString(left_x + 38 * mm, info_y - 10 * mm, rec["sexo"])
    c.drawString(right_x + 28 * mm, info_y, rec["indicacao"])
    c.drawString(right_x + 28 * mm, info_y - 5 * mm, rec["exame_em"].strftime("%d/%m/%Y"))
    c.drawString(right_x + 28 * mm, info_y - 10 * mm, rec["convenio"])

    c.setStrokeColor(BLUE)
    c.setLineWidth(0.6)
    line_y = info_y - 14 * mm
    c.line(margin, line_y, w - margin, line_y)

    styles = {
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=BLUE_DARK),
        "b": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=black),
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_JUSTIFY, textColor=black),
        "li": ParagraphStyle("li", fontName="Helvetica", fontSize=9, leading=12, leftIndent=8, textColor=black),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=GRAY, alignment=TA_CENTER),
    }

    story = []
    exam = rec["exam"]
    var = rec["variant"]
    story.append(_wrap(exam["secao"], styles["h"]))
    story.append(_wrap("Conclusões:", styles["b"]))

    if exam["layout"] == "eeg":
        story.append(_wrap("A) Especificações técnicas do exame", styles["b"]))
        story.append(_wrap(var["tecnica"], styles["p"]))
        story.append(_wrap("B) Resultados obtidos", styles["b"]))
        for line in var["resultados"]:
            story.append(_wrap(f"- {line}", styles["li"]))
        story.append(_wrap("C) Conclusão", styles["b"]))
        story.append(_wrap(var["conclusao"], styles["p"]))
        consideracao = var["conclusao"]
    else:
        story.append(_wrap("Análise:", styles["b"]))
        for line in var["analise"]:
            story.append(_wrap(f"- {line}", styles["li"]))
        story.append(_wrap("Considerações:", styles["b"]))
        story.append(_wrap(var["consideracoes"], styles["p"]))
        consideracao = var["consideracoes"]

    story.append(
        _wrap(
            "Documento sintético gerado para fins educacionais e de treinamento de modelos. "
            "Não corresponde a paciente, exame ou ato médico reais.",
            styles["note"],
        )
    )

    frame = Frame(margin, 38 * mm, w - 2 * margin, line_y - 42 * mm, showBoundary=0)
    frame.addFromList(story, c)

    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    d = rec["exame_em"]
    data_extenso = f"{rec['cidade']}, {d.day} de {meses[d.month - 1]} de {d.year} às {rec['hora'].strftime('%H:%M')}hs."
    c.setFillColor(black)
    c.setFont("Helvetica", 9)
    c.drawString(margin, 32 * mm, data_extenso)

    med_nome, _, esp = rec["medico"]
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(w - margin, 28 * mm, med_nome)
    c.setFont("Helvetica", 8)
    c.drawRightString(w - margin, 23 * mm, f"CRM {rec['uf']} {rec['crm']} / RQE: {rec['rqe']} - {esp}")

    _draw_seal(c, margin + 18 * mm, 22 * mm, 11 * mm)

    c.setFillColor(LIGHT_GRAY)
    c.rect(0, 0, w, 16 * mm, stroke=0, fill=1)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, 9 * mm, "Para validar este documento acesse: app.maislaudo.com.br/Valideseulaudo")
    c.drawCentredString(w / 2, 4.5 * mm, f"Informe o token: {rec['token']}  |  Documento ficticio para fins educacionais")

    c.showPage()
    c.save()
    return consideracao


def slugify(text: str) -> str:
    trans = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
    text = text.translate(trans).lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:40]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("*.pdf"):
        old.unlink()

    rng = random.Random(SEED)
    index_path = OUTPUT_DIR / "index.csv"
    rows = ["arquivo;exame;paciente;conclusao"]

    for i in range(1, COUNT + 1):
        rec = build_record(rng, i)
        slug = rec["exam"]["slug"]
        filename = f"laudo_{i:03d}_{slug}.pdf"
        path = OUTPUT_DIR / filename
        file_rng = random.Random(SEED + i)
        consideracao = render_pdf(path, rec, file_rng)
        safe = consideracao.replace(";", ",")
        rows.append(f"{filename};{rec['exam']['titulo']};{rec['nome']};{safe}")
        if i % 50 == 0:
            print(f"Gerados {i}/{COUNT} PDFs...")

    index_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Concluído: {COUNT} PDFs em {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
