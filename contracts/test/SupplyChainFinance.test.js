const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("TrustChain SCM - SupplyChainFinance Contract", function () {
  let SupplyChainFinance;
  let scmContract;
  let owner, supplier, buyer, lender, otherAccount;

  const INVOICE_ID_1 = "INV-TEST-001";
  const INVOICE_ID_2 = "INV-TEST-002";
  const AMOUNT_ETH = ethers.parseEther("10"); // 10 tokens / units
  const DUE_DATE = Math.floor(Date.now() / 1000) + 86400 * 30; // 30 days ahead

  beforeEach(async function () {
    [owner, supplier, buyer, lender, otherAccount] = await ethers.getSigners();
    SupplyChainFinance = await ethers.getContractFactory("SupplyChainFinance");
    scmContract = await SupplyChainFinance.deploy();
    await scmContract.waitForDeployment();
  });

  describe("1. Invoice Registration", function () {
    it("should successfully register an invoice and emit InvoiceCreated event", async function () {
      const tx = await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Aerospace Turbine Blades");

      await expect(tx)
        .to.emit(scmContract, "InvoiceCreated")
        .withArgs(
          INVOICE_ID_1,
          supplier.address,
          buyer.address,
          AMOUNT_ETH,
          DUE_DATE,
          "Aerospace Turbine Blades",
          await ethers.provider.getBlock("latest").then((b) => b.timestamp)
        );

      const count = await scmContract.getInvoiceCount();
      expect(count).to.equal(1);

      const inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.invoiceId).to.equal(INVOICE_ID_1);
      expect(inv.supplier).to.equal(supplier.address);
      expect(inv.buyer).to.equal(buyer.address);
      expect(inv.amount).to.equal(AMOUNT_ETH);
      expect(inv.status).to.equal(0); // Created
    });

    it("should reject duplicate invoice ID", async function () {
      await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Test Item");

      await expect(
        scmContract
          .connect(supplier)
          .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Test Item")
      ).to.be.revertedWith("TrustChain: Invoice ID already exists");
    });

    it("should reject invoice where buyer is equal to supplier", async function () {
      await expect(
        scmContract
          .connect(supplier)
          .createInvoice(INVOICE_ID_1, supplier.address, AMOUNT_ETH, DUE_DATE, "Self Trade")
      ).to.be.revertedWith("TrustChain: Buyer cannot be supplier");
    });
  });

  describe("2. Shipment Confirmation", function () {
    beforeEach(async function () {
      await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Test Goods");
    });

    it("should allow supplier or buyer to confirm shipment and emit ShipmentConfirmed", async function () {
      const tx = await scmContract
        .connect(supplier)
        .confirmShipment(INVOICE_ID_1, "DHL Express", "DHL-987654321");

      await expect(tx)
        .to.emit(scmContract, "ShipmentConfirmed")
        .withArgs(
          INVOICE_ID_1,
          "DHL Express",
          "DHL-987654321",
          await ethers.provider.getBlock("latest").then((b) => b.timestamp)
        );

      const inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.status).to.equal(1); // ShipmentConfirmed
      expect(inv.carrier).to.equal("DHL Express");
      expect(inv.trackingNumber).to.equal("DHL-987654321");
    });

    it("should reject unauthorized account from confirming shipment", async function () {
      await expect(
        scmContract
          .connect(otherAccount)
          .confirmShipment(INVOICE_ID_1, "Fake Carrier", "FAKE-000")
      ).to.be.revertedWith("TrustChain: Only supplier or buyer can confirm shipment");
    });
  });

  describe("3. Financing Lifecycle", function () {
    beforeEach(async function () {
      await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Test Goods");
    });

    it("should allow supplier to request financing and lender to approve", async function () {
      await scmContract.connect(supplier).requestFinancing(INVOICE_ID_1, AMOUNT_ETH);
      let inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.status).to.equal(2); // FinancingRequested

      await scmContract.connect(lender).approveFinancing(INVOICE_ID_1, 250); // 2.50% interest
      inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.status).to.equal(3); // Financed
      expect(inv.lender).to.equal(lender.address);
    });
  });

  describe("4. Payment Release", function () {
    beforeEach(async function () {
      await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Test Goods");
    });

    it("should allow buyer to release payment and emit PaymentReleased event", async function () {
      const tx = await scmContract.connect(buyer).releasePayment(INVOICE_ID_1);

      await expect(tx)
        .to.emit(scmContract, "PaymentReleased")
        .withArgs(
          INVOICE_ID_1,
          buyer.address,
          AMOUNT_ETH,
          await ethers.provider.getBlock("latest").then((b) => b.timestamp)
        );

      const inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.status).to.equal(4); // Paid
    });
  });

  describe("5. AI Risk Score Updates & Fraud Mitigation", function () {
    beforeEach(async function () {
      await scmContract
        .connect(supplier)
        .createInvoice(INVOICE_ID_1, buyer.address, AMOUNT_ETH, DUE_DATE, "Suspicious Goods");
    });

    it("should record risk score and flag invoice on-chain when anomaly detected", async function () {
      const tx = await scmContract
        .connect(owner)
        .updateRiskScore(INVOICE_ID_1, 94, true, "Ghost shipment anomaly detected");

      await expect(tx)
        .to.emit(scmContract, "RiskScoreUpdated")
        .withArgs(
          INVOICE_ID_1,
          94,
          true,
          "Ghost shipment anomaly detected",
          await ethers.provider.getBlock("latest").then((b) => b.timestamp)
        );

      const inv = await scmContract.getInvoice(INVOICE_ID_1);
      expect(inv.riskScore).to.equal(94);
      expect(inv.isFlagged).to.equal(true);
      expect(inv.status).to.equal(5); // FlaggedFraud
    });
  });
});
