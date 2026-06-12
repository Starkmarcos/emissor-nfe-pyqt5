# 📄 Emissor NF-e Profissional

Sistema desktop desenvolvido em Python para emissão e gerenciamento de Notas Fiscais Eletrônicas (NF-e) de forma simplificada.

## 🚀 Funcionalidades

### 👥 Clientes

* Cadastro de clientes
* CPF/CNPJ
* Endereço
* Telefone
* E-mail

### 📦 Produtos

* Cadastro de produtos
* Controle de estoque
* Código interno
* Unidade de medida
* Atualização e exclusão de registros

### 💰 Vendas

* Seleção de clientes
* Inclusão de múltiplos produtos
* Cálculo automático de totais
* Histórico de vendas

### 📄 Emissão de Documentos

* Geração automática de PDF
* Geração automática de XML
* Pré-visualização do XML
* Simulação de envio da NF-e

### 🔐 Certificado Digital

* Configuração de certificados A1 e A3
* Validação de arquivo PFX/P12
* Assinatura simulada para ambiente de demonstração

### 🗄️ Banco de Dados

* SQLite
* Criação automática das tabelas
* Migração automática de estrutura

## 🛠️ Tecnologias Utilizadas

* Python
* PyQt5
* SQLite
* FPDF2
* LXML
* OpenSSL

## ▶️ Instalação

Instale as dependências:

```bash
pip install pyqt5 fpdf2 lxml pyopenssl
```

Execute o sistema:

```bash
python sistema_nfe.py
```

## 📸 Imagens do Sistema

Adicione aqui capturas das telas de:

* Clientes
* Produtos
* Vendas
* Configurações
* Emissão de NF-e

## 👨‍💻 Autor

Marcos Stark

Projeto desenvolvido para estudo, automação empresarial e gerenciamento de emissão de documentos fiscais.
