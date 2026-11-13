"""Gera um zip no formato INLABS com atos fictícios, para testar o filtro."""
import zipfile, sys
from pathlib import Path

ATOS = [
 ("1","Instrução Normativa","Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil",
  "INSTRUÇÃO NORMATIVA RFB Nº 9.999, DE 12 DE NOVEMBRO DE 2026",
  '<p class="ementa">Dispõe sobre a apuração da CBS de que trata a Lei Complementar nº 214, de 16 de janeiro de 2025.</p><p>Art. 1º ...</p>'),
 ("2","Portaria","Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil",
  "PORTARIA RFB Nº 1.234, DE 12 DE NOVEMBRO DE 2026",
  "<p>O Secretário resolve: Nomear FULANO para exercer o cargo de Delegado...</p>"),
 ("3","Decreto","Atos do Poder Executivo","DECRETO Nº 12.999, DE 12 DE NOVEMBRO DE 2026",
  "<p>Dispõe sobre o saneamento no município de Anápolis e no principal município do Estado.</p>"),
 ("4","Ato Conjunto","Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil",
  "ATO CONJUNTO RFB/CGIBS Nº 9, DE 12 DE NOVEMBRO DE 2026",
  '<p class="ementa">Altera o cronograma de destaque do IBS e da CBS nos documentos fiscais eletrônicos.</p>'),
 ("5","Solução de Consulta","Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil/Coordenação-Geral de Tributação",
  "SOLUÇÃO DE CONSULTA COSIT Nº 200, DE 10 DE NOVEMBRO DE 2026",
  "<p>ASSUNTO: IMPOSTO SOBRE A RENDA DE PESSOA JURÍDICA - IRPJ. Lucro presumido...</p>"),
 ("6","Ato Declaratório Executivo","Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil/Superintendência Regional da 1ª Região Fiscal",
  "ATO DECLARATÓRIO EXECUTIVO Nº 50, DE 11 DE NOVEMBRO DE 2026",
  "<p>Habilita a empresa XYZ LTDA ao Reporto.</p>"),
 ("7","Convênio","Ministério da Fazenda/Conselho Nacional de Política Fazendária",
  "CONVÊNIO ICMS Nº 150, DE 7 DE NOVEMBRO DE 2026",
  "<p>Autoriza o Estado de Goiás a conceder isenção do ICMS nas operações...</p>"),
 ("8","Portaria","Ministério da Saúde/Gabinete do Ministro","PORTARIA GM/MS Nº 7.000, DE 12 DE NOVEMBRO DE 2026",
  "<p>Lista medicamentos com redução a zero das alíquotas de que trata o art. 146 da Lei Complementar n° 214, de 2025.</p>"),
 ("9","Portaria","Ministério da Educação","PORTARIA MEC Nº 10, DE 12 DE NOVEMBRO DE 2026",
  "<p>Aprova o calendário escolar. Os ibs-alunos... a vibs.</p>"),
]
TPL = '''<xml><article id="{id}" name="ato{id}" pubName="DO1" artType="{tipo}" pubDate="13/11/2026" artCategory="{org}" numberPage="{id}0" pdfPage="http://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=13/11/2026&amp;jornal=515&amp;pagina={id}0" editionNumber="218"><body><Identifica><![CDATA[{tit}]]></Identifica><Data><![CDATA[]]></Data><Ementa><![CDATA[]]></Ementa><Titulo/><SubTitulo/><Texto><![CDATA[{txt}]]></Texto></body><Midias/></article></xml>'''
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "2026-11-13-DO1.zip", "w") as z:
    for i,(id_,tipo,org,tit,txt) in enumerate(ATOS):
        z.writestr(f"515_20261113_{id_}.xml", TPL.format(id=id_,tipo=tipo,org=org,tit=tit,txt=txt))
print("ok")
