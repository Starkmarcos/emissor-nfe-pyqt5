# sistema_nfe.py
# Dependências:
# pip install pyqt5 fpdf2 lxml pyopenssl

import sys, sqlite3, datetime, os, base64
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from fpdf import FPDF
from lxml import etree
from OpenSSL import crypto

DB_NAME = "sistema_nfe.db"

# --------------------- Banco de Dados com Migração ---------------------
def conectar():
    return sqlite3.connect(DB_NAME)

def criar_tabelas():
    conn = conectar()
    c = conn.cursor()

    # clientes
    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cpf_cnpj TEXT NOT NULL UNIQUE,
        endereco TEXT,
        telefone TEXT,
        email TEXT
    )""")

    # produtos
    c.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL UNIQUE,
        descricao TEXT NOT NULL,
        preco REAL NOT NULL,
        estoque INTEGER NOT NULL,
        unidade TEXT NOT NULL
    )""")

    # vendas (base)
    c.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        data TEXT,
        total REAL,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )""")

    # itens_venda
    c.execute("""
    CREATE TABLE IF NOT EXISTS itens_venda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venda_id INTEGER,
        produto_id INTEGER,
        quantidade INTEGER,
        preco_unit REAL,
        FOREIGN KEY(venda_id) REFERENCES vendas(id),
        FOREIGN KEY(produto_id) REFERENCES produtos(id)
    )""")

    # configuracoes
    c.execute("""
    CREATE TABLE IF NOT EXISTS configuracoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_certificado TEXT,
        caminho_certificado TEXT,
        senha TEXT
    )""")

    # função utilitária para adicionar coluna se não existir
    def add_column_if_not_exists(table, column, coltype):
        c.execute(f"PRAGMA table_info({table})")
        cols = [info[1] for info in c.fetchall()]
        if column not in cols:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            except Exception as e:
                print(f"Aviso ao adicionar coluna {column} em {table}: {e}")

    # Colunas extras (migração)
    add_column_if_not_exists("vendas", "enviado", "INTEGER DEFAULT 0")
    add_column_if_not_exists("vendas", "pdf_path", "TEXT")
    add_column_if_not_exists("vendas", "xml_path", "TEXT")

    conn.commit()
    conn.close()

# --------------------- Util: PDF e XML ---------------------
def gerar_pdf(venda_id, cliente, itens, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"NF-e Venda #{venda_id}", ln=True, align="C")
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True)
    pdf.cell(0, 7, f"Cliente: {cliente['nome']}  -  {cliente['cpf_cnpj']}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(100, 8, "Descrição", border=1)
    pdf.cell(30, 8, "Qtd", border=1, align="R")
    pdf.cell(30, 8, "Unit", border=1, align="R")
    pdf.cell(30, 8, "Total", border=1, align="R", ln=True)

    pdf.set_font("Arial", "", 11)
    for it in itens:
        pdf.cell(100, 8, it["descricao"], border=1)
        pdf.cell(30, 8, str(it["quantidade"]), border=1, align="R")
        pdf.cell(30, 8, f"R$ {it['preco_unit']:.2f}", border=1, align="R")
        pdf.cell(30, 8, f"R$ {it['quantidade']*it['preco_unit']:.2f}", border=1, align="R", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total: R$ {total:.2f}", ln=True, align="R")

    filename = f"NF-e_{venda_id}.pdf"
    pdf.output(filename)
    return os.path.abspath(filename)

def gerar_nfe_xml(venda_id, cliente, itens, total, config):
    # Estrutura simplificada e compatível para demonstração.
    nfe = etree.Element("NFe")
    infNFe = etree.SubElement(nfe, "infNFe")
    etree.SubElement(infNFe, "id").text = f"NFe{venda_id:09d}"
    ide = etree.SubElement(infNFe, "ide")
    etree.SubElement(ide, "dhEmi").text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
    emit = etree.SubElement(infNFe, "emit")
    etree.SubElement(emit, "xNome").text = "Minha Empresa LTDA"
    dest = etree.SubElement(infNFe, "dest")
    etree.SubElement(dest, "xNome").text = cliente['nome']
    etree.SubElement(dest, "CPF_CNPJ").text = cliente['cpf_cnpj']
    dets = etree.SubElement(infNFe, "det")
    for i, item in enumerate(itens, start=1):
        det = etree.SubElement(dets, "prod")
        etree.SubElement(det, "nItem").text = str(i)
        etree.SubElement(det, "xProd").text = item["descricao"]
        etree.SubElement(det, "qCom").text = str(item["quantidade"])
        etree.SubElement(det, "vUnCom").text = f"{item['preco_unit']:.2f}"
        etree.SubElement(det, "vProd").text = f"{item['quantidade']*item['preco_unit']:.2f}"
    total_el = etree.SubElement(infNFe, "total")
    etree.SubElement(total_el, "vNF").text = f"{total:.2f}"

    xml_str = etree.tostring(nfe, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    # Assinatura simulada (se A1 configurado) - apenas para demonstração local
    if config and config.get('caminho_certificado') and os.path.exists(config['caminho_certificado']):
        try:
            with open(config['caminho_certificado'], 'rb') as f:
                pfx = f.read()
            _ = crypto.load_pkcs12(pfx, config['senha'].encode())
            assinatura = base64.b64encode(xml_str).decode()
            root = etree.fromstring(xml_str)
            etree.SubElement(root, "assinatura_simulada").text = assinatura
            xml_str = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        except Exception as e:
            print("Aviso: falha ao assinar XML (simulado):", e)

    filename = f"NF-e_{venda_id}.xml"
    with open(filename, "wb") as f:
        f.write(xml_str)
    return os.path.abspath(filename)

# --------------------- Aba Configurações ---------------------
class ConfiguracoesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ConfigPage")
        layout = QVBoxLayout()

        titulo = QLabel("Configurações do Certificado Digital")
        titulo.setObjectName("Title")
        layout.addWidget(titulo)

        form = QFormLayout()
        self.tipo_cert = QComboBox()
        self.tipo_cert.addItems(["A1", "A3"])
        self.caminho_cert = QLineEdit()
        self.btn_procurar = QPushButton("Procurar Certificado (.pfx/.p12)")
        self.btn_procurar.clicked.connect(self.procurar_cert)
        self.senha_cert = QLineEdit()
        self.senha_cert.setEchoMode(QLineEdit.Password)

        hw1 = QHBoxLayout()
        hw1.addWidget(self.caminho_cert)
        hw1.addWidget(self.btn_procurar)

        form.addRow("Tipo de Certificado:", self.tipo_cert)
        form.addRow("Arquivo:", QWidget())
        form.itemAt(form.rowCount()-1, QFormLayout.FieldRole).widget().setLayout(hw1)
        form.addRow("Senha:", self.senha_cert)
        layout.addLayout(form)

        self.btn_salvar = QPushButton("Salvar Configurações")
        self.btn_salvar.clicked.connect(self.salvar_config)
        layout.addWidget(self.btn_salvar, alignment=Qt.AlignRight)

        layout.addStretch()
        self.setLayout(layout)
        self.carregar_config()

    def procurar_cert(self):
        arq, _ = QFileDialog.getOpenFileName(self, "Selecione o Certificado", "", "Certificado (*.pfx *.p12)")
        if arq:
            self.caminho_cert.setText(arq)

    def salvar_config(self):
        tipo = self.tipo_cert.currentText()
        caminho = self.caminho_cert.text().strip()
        senha = self.senha_cert.text()
        if not caminho or not senha:
            QMessageBox.warning(self, "Campos obrigatórios", "Informe o arquivo e a senha do certificado.")
            return
        conn = conectar()
        c = conn.cursor()
        c.execute("DELETE FROM configuracoes")
        c.execute("INSERT INTO configuracoes (tipo_certificado, caminho_certificado, senha) VALUES (?,?,?)",
                  (tipo, caminho, senha))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Sucesso", "Configurações salvas.")

    def carregar_config(self):
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT tipo_certificado, caminho_certificado, senha FROM configuracoes LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            self.tipo_cert.setCurrentText(row[0] or "A1")
            self.caminho_cert.setText(row[1] or "")
            self.senha_cert.setText(row[2] or "")

# --------------------- Dialog Visualizar XML ---------------------
class VisualizarXMLDialog(QDialog):
    def __init__(self, xml_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pré-visualização da NF-e (XML)")
        self.setMinimumSize(820, 520)
        layout = QVBoxLayout(self)

        info = QLabel(f"Arquivo: {xml_path}")
        info.setObjectName("SubTitle")
        layout.addWidget(info)

        self.viewer = QTextEdit(readOnly=True)
        self.viewer.setObjectName("CodeView")
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                self.viewer.setPlainText(f.read())
        except:
            with open(xml_path, "rb") as f:
                self.viewer.setPlainText(f.read().decode("utf-8", errors="ignore"))
        layout.addWidget(self.viewer, 1)

        btns = QHBoxLayout()
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_confirmar = QPushButton("Confirmar Envio")
        self.btn_confirmar.setObjectName("PrimaryButton")
        btns.addStretch()
        btns.addWidget(self.btn_cancelar)
        btns.addWidget(self.btn_confirmar)
        layout.addLayout(btns)

        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_confirmar.clicked.connect(self.accept)

# --------------------- Janela Principal ---------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emissor NF-e Profissional")
        self.setMinimumSize(1100, 700)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.setCentralWidget(self.tabs)

        # Abas
        self.tab_clientes = QWidget()
        self.tab_produtos = QWidget()
        self.tab_vendas = QWidget()
        self.tab_relatorios = QWidget()
        self.tab_config = ConfiguracoesWindow()

        self.tabs.addTab(self.tab_clientes, "Clientes")
        self.tabs.addTab(self.tab_produtos, "Produtos")
        self.tabs.addTab(self.tab_vendas, "Vendas")
        self.tabs.addTab(self.tab_relatorios, "Relatórios")
        self.tabs.addTab(self.tab_config, "Configurações")

        self.editando_cliente_id = None
        self.editando_produto_id = None
        self.itens_venda = []

        self.init_clientes()
        self.init_produtos()
        self.init_vendas()
        self.init_relatorios()
        self.recarregar_combos()
        self.carregar_tabelas_clientes_produtos()
        self.carregar_tabela_vendas()

    # ----------------- Clientes -----------------
    def init_clientes(self):
        layout = QVBoxLayout()
        titulo = QLabel("Cadastro de Clientes")
        titulo.setObjectName("Title")
        layout.addWidget(titulo)

        form = QFormLayout()
        self.cli_nome = QLineEdit()
        self.cli_cpf = QLineEdit()
        self.cli_end = QLineEdit()
        self.cli_tel = QLineEdit()
        self.cli_email = QLineEdit()
        form.addRow("Nome:", self.cli_nome)
        form.addRow("CPF/CNPJ:", self.cli_cpf)
        form.addRow("Endereço:", self.cli_end)
        form.addRow("Telefone:", self.cli_tel)
        form.addRow("E-mail:", self.cli_email)

        btns = QHBoxLayout()
        self.btn_salvar_cli = QPushButton("Salvar Cliente")
        self.btn_salvar_cli.setObjectName("PrimaryButton")
        self.btn_cancelar_cli = QPushButton("Limpar")
        btns.addWidget(self.btn_salvar_cli)
        btns.addWidget(self.btn_cancelar_cli)
        layout.addLayout(form)
        layout.addLayout(btns)

        self.table_clientes = QTableWidget(0, 6)
        self.table_clientes.setHorizontalHeaderLabels(["ID", "Nome", "CPF/CNPJ", "Endereço", "Telefone", "E-mail"])
        self.table_clientes.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_clientes, 1)

        hb = QHBoxLayout()
        self.btn_editar_cli = QPushButton("Editar Selecionado")
        self.btn_remover_cli = QPushButton("Remover Selecionado")
        hb.addStretch()
        hb.addWidget(self.btn_editar_cli)
        hb.addWidget(self.btn_remover_cli)
        layout.addLayout(hb)

        self.tab_clientes.setLayout(layout)

        # conexões
        self.btn_salvar_cli.clicked.connect(self.salvar_ou_atualizar_cliente)
        self.btn_cancelar_cli.clicked.connect(self.limpar_form_cliente)
        self.btn_editar_cli.clicked.connect(self.editar_cliente)
        self.btn_remover_cli.clicked.connect(self.remover_cliente)

    def salvar_ou_atualizar_cliente(self):
        nome = self.cli_nome.text().strip()
        cpf = self.cli_cpf.text().strip()
        if not nome or not cpf:
            QMessageBox.warning(self, "Campos obrigatórios", "Informe Nome e CPF/CNPJ.")
            return
        conn = conectar()
        c = conn.cursor()
        try:
            if self.editando_cliente_id:
                c.execute("""UPDATE clientes
                             SET nome=?, cpf_cnpj=?, endereco=?, telefone=?, email=?
                             WHERE id=?""",
                          (nome, cpf, self.cli_end.text(), self.cli_tel.text(), self.cli_email.text(), self.editando_cliente_id))
                msg = "Cliente atualizado."
            else:
                c.execute("""INSERT INTO clientes (nome, cpf_cnpj, endereco, telefone, email)
                             VALUES (?,?,?,?,?)""",
                          (nome, cpf, self.cli_end.text(), self.cli_tel.text(), self.cli_email.text()))
                msg = "Cliente cadastrado."
            conn.commit()
            QMessageBox.information(self, "OK", msg)
            self.limpar_form_cliente()
            self.carregar_tabelas_clientes_produtos()
            self.recarregar_combos()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível salvar: {e}")
        finally:
            conn.close()

    def limpar_form_cliente(self):
        self.editando_cliente_id = None
        self.cli_nome.clear()
        self.cli_cpf.clear()
        self.cli_end.clear()
        self.cli_tel.clear()
        self.cli_email.clear()
        self.btn_salvar_cli.setText("Salvar Cliente")

    def editar_cliente(self):
        row = self.table_clientes.currentRow()
        if row < 0:
            return
        self.editando_cliente_id = int(self.table_clientes.item(row, 0).text())
        self.cli_nome.setText(self.table_clientes.item(row, 1).text())
        self.cli_cpf.setText(self.table_clientes.item(row, 2).text())
        self.cli_end.setText(self.table_clientes.item(row, 3).text())
        self.cli_tel.setText(self.table_clientes.item(row, 4).text())
        self.cli_email.setText(self.table_clientes.item(row, 5).text())
        self.btn_salvar_cli.setText("Atualizar Cliente")

    def remover_cliente(self):
        row = self.table_clientes.currentRow()
        if row < 0:
            return
        cid = int(self.table_clientes.item(row, 0).text())
        if QMessageBox.question(self, "Confirmar", "Remover este cliente?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.No:
            return
        conn = conectar()
        c = conn.cursor()
        try:
            c.execute("DELETE FROM clientes WHERE id=?", (cid,))
            conn.commit()
            self.carregar_tabelas_clientes_produtos()
            self.recarregar_combos()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível remover: {e}")
        finally:
            conn.close()

    # ----------------- Produtos -----------------
    def init_produtos(self):
        layout = QVBoxLayout()
        titulo = QLabel("Cadastro de Produtos")
        titulo.setObjectName("Title")
        layout.addWidget(titulo)

        form = QFormLayout()
        self.prod_codigo = QLineEdit()
        self.prod_desc = QLineEdit()
        self.prod_preco = QLineEdit()
        self.prod_estoque = QLineEdit()
        self.prod_unid = QLineEdit()
        form.addRow("Código:", self.prod_codigo)
        form.addRow("Descrição:", self.prod_desc)
        form.addRow("Preço:", self.prod_preco)
        form.addRow("Estoque:", self.prod_estoque)
        form.addRow("Unidade:", self.prod_unid)

        btns = QHBoxLayout()
        self.btn_salvar_prod = QPushButton("Salvar Produto")
        self.btn_salvar_prod.setObjectName("PrimaryButton")
        self.btn_cancelar_prod = QPushButton("Limpar")
        btns.addWidget(self.btn_salvar_prod)
        btns.addWidget(self.btn_cancelar_prod)
        layout.addLayout(form)
        layout.addLayout(btns)

        self.table_produtos = QTableWidget(0, 6)
        self.table_produtos.setHorizontalHeaderLabels(["ID", "Código", "Descrição", "Preço", "Estoque", "Unidade"])
        self.table_produtos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_produtos, 1)

        hb = QHBoxLayout()
        self.btn_editar_prod = QPushButton("Editar Selecionado")
        self.btn_remover_prod = QPushButton("Remover Selecionado")
        hb.addStretch()
        hb.addWidget(self.btn_editar_prod)
        hb.addWidget(self.btn_remover_prod)
        layout.addLayout(hb)

        self.tab_produtos.setLayout(layout)

        # conexões
        self.btn_salvar_prod.clicked.connect(self.salvar_ou_atualizar_produto)
        self.btn_cancelar_prod.clicked.connect(self.limpar_form_produto)
        self.btn_editar_prod.clicked.connect(self.editar_produto)
        self.btn_remover_prod.clicked.connect(self.remover_produto)

    def salvar_ou_atualizar_produto(self):
        try:
            preco = float(self.prod_preco.text().replace(",", "."))
            estoque = int(self.prod_estoque.text())
        except:
            QMessageBox.warning(self, "Erro", "Preço ou estoque inválido.")
            return
        conn = conectar()
        c = conn.cursor()
        try:
            if self.editando_produto_id:
                c.execute("""UPDATE produtos
                             SET codigo=?, descricao=?, preco=?, estoque=?, unidade=?
                             WHERE id=?""",
                          (self.prod_codigo.text(), self.prod_desc.text(), preco, estoque, self.prod_unid.text(), self.editando_produto_id))
                msg = "Produto atualizado."
            else:
                c.execute("""INSERT INTO produtos (codigo, descricao, preco, estoque, unidade)
                             VALUES (?,?,?,?,?)""",
                          (self.prod_codigo.text(), self.prod_desc.text(), preco, estoque, self.prod_unid.text()))
                msg = "Produto cadastrado."
            conn.commit()
            QMessageBox.information(self, "OK", msg)
            self.limpar_form_produto()
            self.carregar_tabelas_clientes_produtos()
            self.recarregar_combos()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar: {e}")
        finally:
            conn.close()

    def limpar_form_produto(self):
        self.editando_produto_id = None
        self.prod_codigo.clear()
        self.prod_desc.clear()
        self.prod_preco.clear()
        self.prod_estoque.clear()
        self.prod_unid.clear()
        self.btn_salvar_prod.setText("Salvar Produto")

    def editar_produto(self):
        row = self.table_produtos.currentRow()
        if row < 0:
            return
        self.editando_produto_id = int(self.table_produtos.item(row, 0).text())
        self.prod_codigo.setText(self.table_produtos.item(row, 1).text())
        self.prod_desc.setText(self.table_produtos.item(row, 2).text())
        self.prod_preco.setText(self.table_produtos.item(row, 3).text())
        self.prod_estoque.setText(self.table_produtos.item(row, 4).text())
        self.prod_unid.setText(self.table_produtos.item(row, 5).text())
        self.btn_salvar_prod.setText("Atualizar Produto")

    def remover_produto(self):
        row = self.table_produtos.currentRow()
        if row < 0:
            return
        pid = int(self.table_produtos.item(row, 0).text())
        if QMessageBox.question(self, "Confirmar", "Remover este produto?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.No:
            return
        conn = conectar()
        c = conn.cursor()
        try:
            c.execute("DELETE FROM produtos WHERE id=?", (pid,))
            conn.commit()
            self.carregar_tabelas_clientes_produtos()
            self.recarregar_combos()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível remover: {e}")
        finally:
            conn.close()

    # ----------------- Vendas -----------------
    def init_vendas(self):
        layout = QVBoxLayout()
        titulo = QLabel("Emissão de NF-e (Simulada)")
        titulo.setObjectName("Title")
        layout.addWidget(titulo)

        form = QGridLayout()
        form.addWidget(QLabel("Cliente:"), 0, 0)
        self.cb_cliente = QComboBox()
        form.addWidget(self.cb_cliente, 0, 1, 1, 3)

        form.addWidget(QLabel("Produto:"), 1, 0)
        self.cb_produto = QComboBox()
        form.addWidget(self.cb_produto, 1, 1, 1, 2)

        self.inp_qtd = QLineEdit()
        self.inp_qtd.setPlaceholderText("Quantidade")
        form.addWidget(self.inp_qtd, 1, 3)

        self.btn_add_item = QPushButton("Adicionar Item")
        self.btn_add_item.setObjectName("SecondaryButton")
        form.addWidget(self.btn_add_item, 1, 4)

        layout.addLayout(form)

        self.table_itens = QTableWidget(0, 4)
        self.table_itens.setHorizontalHeaderLabels(["Produto", "Qtd", "Preço Unit.", "Total"])
        self.table_itens.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_itens, 1)

        hb = QHBoxLayout()
        self.lbl_total = QLabel("Total: R$ 0,00")
        hb.addWidget(self.lbl_total)
        hb.addStretch()
        self.btn_finalizar = QPushButton("Finalizar (Gerar PDF + XML)")
        self.btn_finalizar.setObjectName("PrimaryButton")
        hb.addWidget(self.btn_finalizar)
        layout.addLayout(hb)

        hist_title = QLabel("Histórico de Vendas")
        hist_title.setObjectName("SubTitle")
        layout.addWidget(hist_title)
        self.table_vendas = QTableWidget(0, 6)
        self.table_vendas.setHorizontalHeaderLabels(["ID", "Data", "Cliente", "Total", "Enviado", "XML"])
        self.table_vendas.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_vendas, 1)

        hb2 = QHBoxLayout()
        self.btn_visualizar_xml = QPushButton("Visualizar/Enviar NF-e da venda selecionada")
        self.btn_visualizar_xml.setObjectName("AccentButton")
        hb2.addStretch()
        hb2.addWidget(self.btn_visualizar_xml)
        layout.addLayout(hb2)

        self.tab_vendas.setLayout(layout)

        # conexões
        self.btn_add_item.clicked.connect(self.adicionar_item_venda)
        self.btn_finalizar.clicked.connect(self.finalizar_venda)
        self.btn_visualizar_xml.clicked.connect(self.fluxo_visualizar_enviar)

    def recarregar_combos(self):
        conn = conectar()
        c = conn.cursor()
        self.cb_cliente.clear()
        c.execute("SELECT id, nome FROM clientes ORDER BY nome")
        for cid, nome in c.fetchall():
            self.cb_cliente.addItem(nome, cid)
        self.cb_produto.clear()
        c.execute("SELECT id, descricao, preco FROM produtos ORDER BY descricao")
        for pid, desc, preco in c.fetchall():
            self.cb_produto.addItem(f"{desc} (R$ {preco:.2f})", (pid, preco, desc))
        conn.close()

    def carregar_tabelas_clientes_produtos(self):
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT id, nome, cpf_cnpj, endereco, telefone, email FROM clientes ORDER BY id DESC")
        rows = c.fetchall()
        self.table_clientes.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for col, val in enumerate(row):
                self.table_clientes.setItem(r, col, QTableWidgetItem(str(val)))

        c.execute("SELECT id, codigo, descricao, preco, estoque, unidade FROM produtos ORDER BY id DESC")
        rows = c.fetchall()
        self.table_produtos.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for col, val in enumerate(row):
                self.table_produtos.setItem(r, col, QTableWidgetItem(str(val)))
        conn.close()

    def adicionar_item_venda(self):
        if self.cb_produto.count() == 0:
            QMessageBox.warning(self, "Atenção", "Cadastre produtos primeiro.")
            return
        try:
            qtd = int(self.inp_qtd.text())
            if qtd <= 0:
                raise ValueError
        except:
            QMessageBox.warning(self, "Quantidade inválida", "Informe um número inteiro positivo.")
            return
        pid, preco, desc = self.cb_produto.currentData()
        total_item = qtd * float(preco)
        self.itens_venda.append({"produto_id": pid, "descricao": desc, "quantidade": qtd, "preco_unit": float(preco)})

        row = self.table_itens.rowCount()
        self.table_itens.insertRow(row)
        self.table_itens.setItem(row, 0, QTableWidgetItem(desc))
        self.table_itens.setItem(row, 1, QTableWidgetItem(str(qtd)))
        self.table_itens.setItem(row, 2, QTableWidgetItem(f"{preco:.2f}"))
        self.table_itens.setItem(row, 3, QTableWidgetItem(f"{total_item:.2f}"))

        self.inp_qtd.clear()
        self.atualizar_total()

    def atualizar_total(self):
        total = sum(i["quantidade"] * i["preco_unit"] for i in self.itens_venda)
        self.lbl_total.setText(f"Total: R$ {total:.2f}")

    def finalizar_venda(self):
        if not self.itens_venda:
            QMessageBox.warning(self, "Itens", "Adicione itens à venda.")
            return
        if self.cb_cliente.count() == 0:
            QMessageBox.warning(self, "Clientes", "Cadastre clientes primeiro.")
            return

        cliente_id = self.cb_cliente.currentData()
        total = sum(i["quantidade"] * i["preco_unit"] for i in self.itens_venda)
        data = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT nome, cpf_cnpj FROM clientes WHERE id=?", (cliente_id,))
        row = c.fetchone()
        cliente_info = {"nome": row[0], "cpf_cnpj": row[1]}

        c.execute("SELECT tipo_certificado, caminho_certificado, senha FROM configuracoes LIMIT 1")
        cfg = c.fetchone()
        config = None
        if cfg:
            config = {"tipo_certificado": cfg[0] or "A1", "caminho_certificado": cfg[1] or "", "senha": cfg[2] or ""}

        c.execute("INSERT INTO vendas (cliente_id, data, total, enviado) VALUES (?,?,?,0)", (cliente_id, data, total))
        venda_id = c.lastrowid
        for it in self.itens_venda:
            c.execute("""INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unit)
                         VALUES (?,?,?,?)""", (venda_id, it["produto_id"], it["quantidade"], it["preco_unit"]))

        pdf_path = gerar_pdf(venda_id, cliente_info, self.itens_venda, total)
        xml_path = gerar_nfe_xml(venda_id, cliente_info, self.itens_venda, total, config)

        c.execute("UPDATE vendas SET pdf_path=?, xml_path=? WHERE id=?", (pdf_path, xml_path, venda_id))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Venda", f"Venda #{venda_id} finalizada.\nPDF e XML gerados.")
        self.itens_venda.clear()
        self.table_itens.setRowCount(0)
        self.atualizar_total()
        self.carregar_tabela_vendas()

    def carregar_tabela_vendas(self):
        conn = conectar()
        c = conn.cursor()
        c.execute("""
        SELECT v.id, v.data, COALESCE(cl.nome,'(excluído)'), v.total,
               COALESCE(v.enviado,0), COALESCE(v.xml_path,'')
        FROM vendas v
        LEFT JOIN clientes cl ON cl.id = v.cliente_id
        ORDER BY v.id DESC
        """)
        rows = c.fetchall()
        conn.close()
        self.table_vendas.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for col, val in enumerate(row):
                if col == 4:
                    val = "Sim" if int(val) else "Não"
                self.table_vendas.setItem(r, col, QTableWidgetItem(str(val)))

    def fluxo_visualizar_enviar(self):
        row = self.table_vendas.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Seleção", "Selecione uma venda no histórico.")
            return
        venda_id = int(self.table_vendas.item(row, 0).text())
        enviado = self.table_vendas.item(row, 4).text() == "Sim"
        xml_path = self.table_vendas.item(row, 5).text()

        if not xml_path or not os.path.exists(xml_path):
            QMessageBox.warning(self, "XML", "XML não encontrado nesta venda.")
            return

        dlg = VisualizarXMLDialog(xml_path, self)
        if dlg.exec_() == QDialog.Accepted:
            conn = conectar()
            c = conn.cursor()
            c.execute("UPDATE vendas SET enviado=1 WHERE id=?", (venda_id,))
            conn.commit()
            conn.close()
            self.carregar_tabela_vendas()
            QMessageBox.information(self, "SEFAZ", "NF-e enviada com sucesso (simulado).")

    # ----------------- Relatórios (simples placeholders) -----------------
    def init_relatorios(self):
        layout = QVBoxLayout()
        titulo = QLabel("Relatórios")
        titulo.setObjectName("Title")
        layout.addWidget(titulo)
        layout.addWidget(QLabel("Relatório Diário/Mensal e exportação em breve."))
        self.tab_relatorios.setLayout(layout)

# --------------------- QSS (tema) ---------------------
APP_QSS = """
QWidget { background: #f7f9fc; color: #2d3748; font-family: Segoe UI, Arial; font-size: 11pt; }
#Title { font-size: 18pt; font-weight: 700; color: #1a365d; padding: 6px 0 10px 0; }
#SubTitle { font-size: 12.5pt; font-weight: 600; color: #2b6cb0; padding: 4px 0 6px 0; }
QTabWidget::pane { border: 1px solid #d0d7e2; border-radius: 10px; padding: 6px; background: #ffffff; }
QTabBar::tab { background: #e6eef9; color: #243b53; border: 1px solid #cbd5e0; border-bottom: none; padding: 8px 16px; margin-right: 4px; border-top-left-radius: 10px; border-top-right-radius: 10px; }
QTabBar::tab:selected { background: #ffffff; color: #1a365d; font-weight: 600; }
QTabBar::tab:hover { background: #dbe7fb; }
QPushButton { background: #e2e8f0; border: 1px solid #cbd5e0; border-radius: 10px; padding: 8px 14px; }
QPushButton:hover { background: #d9e2ec; }
QPushButton#PrimaryButton { background: #2b6cb0; color: white; border: none; }
QPushButton#PrimaryButton:hover { background: #2c5282; }
QPushButton#SecondaryButton { background: #4a5568; color: white; border: none; }
QPushButton#SecondaryButton:hover { background: #2d3748; }
QPushButton#AccentButton { background: #38a169; color: white; border: none; }
QPushButton#AccentButton:hover { background: #2f855a; }
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #cbd5e0; border-radius: 8px; padding: 6px 8px; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #2b6cb0; }
QTableWidget { background: #ffffff; border: 1px solid #cbd5e0; border-radius: 10px; gridline-color: #e2e8f0; }
QHeaderView::section { background: #edf2f7; padding: 6px; border: 1px solid #cbd5e0; }
QTableWidget::item:selected { background: #bee3f8; }
#CodeView { background: #0b1021; color: #e5e7eb; border: 1px solid #1f2937; border-radius: 10px; font-family: Consolas, "Courier New", monospace; font-size: 10.5pt; }
"""

# --------------------- main ---------------------
def main():
    criar_tabelas()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
