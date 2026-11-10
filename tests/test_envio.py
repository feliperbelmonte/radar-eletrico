import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prospeccao"))
import envio as e  # noqa: E402

LEADS = [{"cnpj": f"{i:02d}111111000111", "empresa": f"E{i}", "celular": f"419999900{i:02d}", "cidade": "Curitiba",
          "uf": "PR", "segmento": "Instalação elétrica", "modelo": 4, "trilha": t,
          "mensagem": "{saudacao}, tudo bem? Aqui é o Felipe."} for i, t in
         enumerate(["projeto"] * 8 + ["licitacao"] * 3 + ["pericia"] * 6)]
PAINEL = "/* LEADS_DATA_START */\nconst LEADS = " + json.dumps(LEADS) + ";\nconst RESUMO = null;\nconst FILA = {\"meta\": 10, \"licitacao\": 5, \"pericia\": 2, \"projeto\": 3};\n/* LEADS_DATA_END */"


class TestEnvio(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "p.html").write_text(PAINEL, encoding="utf-8")
        self.leads, self.cfg = e.ler_painel(self.tmp / "p.html")

    def test_fila_cotas_e_saudacao(self):
        agora = datetime.fromisoformat("2026-11-10T09:00:00-03:00")
        status = {"00111111000111": {"status": "contatado", "contatadoEm": "2026-11-10T11:00:00Z"},
                  "01111111000111": {"status": "pulada"}}
        f = e.montar_fila(self.leads, self.cfg, status, agora)
        self.assertEqual(len(f), 9)                       # meta 10 - 1 já feito hoje
        self.assertEqual([i["trilha"] for i in f[:3]], ["licitacao"] * 3)
        self.assertNotIn("00111111000111", [i["cnpj"] for i in f])
        self.assertNotIn("01111111000111", [i["cnpj"] for i in f])
        self.assertTrue(f[0]["mensagem"].startswith("Bom dia, tudo bem?"))
        self.assertIn("web.whatsapp.com/send?phone=55", f[0]["url"])
        tarde = e.montar_fila(self.leads, self.cfg, {}, datetime.fromisoformat("2026-11-10T15:00:00-03:00"))
        self.assertTrue(tarde[0]["mensagem"].startswith("Boa tarde"))

    def test_marcar(self):
        agora = datetime.fromisoformat("2026-11-10T15:00:00-03:00")
        d = e.doc_contatado(self.leads[2], agora)
        self.assertEqual(d["status"], "contatado")
        self.assertEqual(d["contatadoEm"], "2026-11-10T18:00:00.000Z")
        self.assertEqual(d["celular"], self.leads[2]["celular"])
        p = e.doc_contatado(self.leads[2], agora, pulada="sem WhatsApp")
        self.assertEqual(p["status"], "pulada")
        self.assertNotIn("contatadoEm", p)


if __name__ == "__main__":
    unittest.main()
