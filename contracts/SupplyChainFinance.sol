// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SupplyChainFinance
 * @notice TrustChain SCM - Smart contract for immutable supply chain events,
 *         invoice lifecycle, financing, and fraud mitigation audit trail.
 */
contract SupplyChainFinance {
    enum InvoiceStatus {
        Created,
        ShipmentConfirmed,
        FinancingRequested,
        Financed,
        Paid,
        FlaggedFraud
    }

    struct Invoice {
        string invoiceId;
        address supplier;
        address buyer;
        address lender;
        uint256 amount;
        uint256 dueDate;
        string itemDescription;
        string carrier;
        string trackingNumber;
        InvoiceStatus status;
        uint256 riskScore;       // 0 - 100
        bool isFlagged;
        string flagReason;
        uint256 createdAt;
        uint256 updatedAt;
    }

    // Mapping from invoiceId => Invoice
    mapping(string => Invoice) private invoices;
    string[] private allInvoiceIds;

    // Events as required by TrustChain SCM
    event InvoiceCreated(
        string indexed invoiceId,
        address indexed supplier,
        address indexed buyer,
        uint256 amount,
        uint256 dueDate,
        string itemDescription,
        uint256 timestamp
    );

    event ShipmentConfirmed(
        string indexed invoiceId,
        string carrier,
        string trackingNumber,
        uint256 timestamp
    );

    event FinancingRequested(
        string indexed invoiceId,
        address indexed supplier,
        uint256 requestedAmount,
        uint256 timestamp
    );

    event FinancingApproved(
        string indexed invoiceId,
        address indexed lender,
        uint256 fundedAmount,
        uint256 interestRateBps,
        uint256 timestamp
    );

    event PaymentReleased(
        string indexed invoiceId,
        address indexed buyer,
        uint256 amountPaid,
        uint256 timestamp
    );

    event RiskScoreUpdated(
        string indexed invoiceId,
        uint256 riskScore,
        bool isFlagged,
        string reason,
        uint256 timestamp
    );

    modifier invoiceExists(string memory _invoiceId) {
        require(invoices[_invoiceId].createdAt > 0, "TrustChain: Invoice does not exist");
        _;
    }

    /**
     * @notice Registers a new invoice onto the immutable ledger.
     */
    function createInvoice(
        string memory _invoiceId,
        address _buyer,
        uint256 _amount,
        uint256 _dueDate,
        string memory _itemDescription
    ) external {
        require(bytes(_invoiceId).length > 0, "TrustChain: Invalid invoice ID");
        require(_buyer != address(0), "TrustChain: Invalid buyer address");
        require(_buyer != msg.sender, "TrustChain: Buyer cannot be supplier");
        require(_amount > 0, "TrustChain: Amount must be greater than zero");
        require(_dueDate > block.timestamp, "TrustChain: Due date must be in future");
        require(invoices[_invoiceId].createdAt == 0, "TrustChain: Invoice ID already exists");

        Invoice storage inv = invoices[_invoiceId];
        inv.invoiceId = _invoiceId;
        inv.supplier = msg.sender;
        inv.buyer = _buyer;
        inv.amount = _amount;
        inv.dueDate = _dueDate;
        inv.itemDescription = _itemDescription;
        inv.status = InvoiceStatus.Created;
        inv.createdAt = block.timestamp;
        inv.updatedAt = block.timestamp;

        allInvoiceIds.push(_invoiceId);

        emit InvoiceCreated(
            _invoiceId,
            msg.sender,
            _buyer,
            _amount,
            _dueDate,
            _itemDescription,
            block.timestamp
        );
    }

    /**
     * @notice Confirms dispatch and logistics carrier details for an invoice.
     */
    function confirmShipment(
        string memory _invoiceId,
        string memory _carrier,
        string memory _trackingNumber
    ) external invoiceExists(_invoiceId) {
        Invoice storage inv = invoices[_invoiceId];
        require(
            msg.sender == inv.supplier || msg.sender == inv.buyer,
            "TrustChain: Only supplier or buyer can confirm shipment"
        );
        require(
            inv.status == InvoiceStatus.Created || inv.status == InvoiceStatus.FinancingRequested,
            "TrustChain: Invalid status for shipment confirmation"
        );

        inv.carrier = _carrier;
        inv.trackingNumber = _trackingNumber;
        inv.status = InvoiceStatus.ShipmentConfirmed;
        inv.updatedAt = block.timestamp;

        emit ShipmentConfirmed(_invoiceId, _carrier, _trackingNumber, block.timestamp);
    }

    /**
     * @notice Supplier requests early financing for receivables.
     */
    function requestFinancing(
        string memory _invoiceId,
        uint256 _requestedAmount
    ) external invoiceExists(_invoiceId) {
        Invoice storage inv = invoices[_invoiceId];
        require(msg.sender == inv.supplier, "TrustChain: Only supplier can request financing");
        require(!inv.isFlagged, "TrustChain: Cannot finance flagged invoice");
        require(
            _requestedAmount > 0 && _requestedAmount <= inv.amount,
            "TrustChain: Requested amount exceeds invoice amount"
        );

        inv.status = InvoiceStatus.FinancingRequested;
        inv.updatedAt = block.timestamp;

        emit FinancingRequested(_invoiceId, msg.sender, _requestedAmount, block.timestamp);
    }

    /**
     * @notice Lender approves and funds receivables financing.
     */
    function approveFinancing(
        string memory _invoiceId,
        uint256 _interestRateBps
    ) external payable invoiceExists(_invoiceId) {
        Invoice storage inv = invoices[_invoiceId];
        require(!inv.isFlagged, "TrustChain: Cannot approve flagged invoice");
        require(
            inv.status == InvoiceStatus.FinancingRequested ||
            inv.status == InvoiceStatus.ShipmentConfirmed ||
            inv.status == InvoiceStatus.Created,
            "TrustChain: Invoice not eligible for financing"
        );

        inv.lender = msg.sender;
        inv.status = InvoiceStatus.Financed;
        inv.updatedAt = block.timestamp;

        emit FinancingApproved(_invoiceId, msg.sender, inv.amount, _interestRateBps, block.timestamp);
    }

    /**
     * @notice Buyer releases settlement payment upon delivery/maturity.
     */
    function releasePayment(string memory _invoiceId) external payable invoiceExists(_invoiceId) {
        Invoice storage inv = invoices[_invoiceId];
        require(inv.status != InvoiceStatus.Paid, "TrustChain: Already paid");

        inv.status = InvoiceStatus.Paid;
        inv.updatedAt = block.timestamp;

        emit PaymentReleased(_invoiceId, msg.sender, inv.amount, block.timestamp);
    }

    /**
     * @notice Updates AI risk score and flags anomalies on-chain.
     */
    function updateRiskScore(
        string memory _invoiceId,
        uint256 _riskScore,
        bool _isFlagged,
        string memory _reason
    ) external invoiceExists(_invoiceId) {
        Invoice storage inv = invoices[_invoiceId];
        inv.riskScore = _riskScore;
        inv.isFlagged = _isFlagged;
        inv.flagReason = _reason;
        inv.updatedAt = block.timestamp;

        if (_isFlagged) {
            inv.status = InvoiceStatus.FlaggedFraud;
        }

        emit RiskScoreUpdated(_invoiceId, _riskScore, _isFlagged, _reason, block.timestamp);
    }

    /**
     * @notice Returns complete details for a specific invoice.
     */
    function getInvoice(string memory _invoiceId)
        external
        view
        invoiceExists(_invoiceId)
        returns (
            string memory invoiceId,
            address supplier,
            address buyer,
            address lender,
            uint256 amount,
            uint256 dueDate,
            InvoiceStatus status,
            uint256 riskScore,
            bool isFlagged,
            string memory carrier,
            string memory trackingNumber,
            uint256 createdAt
        )
    {
        Invoice storage inv = invoices[_invoiceId];
        return (
            inv.invoiceId,
            inv.supplier,
            inv.buyer,
            inv.lender,
            inv.amount,
            inv.dueDate,
            inv.status,
            inv.riskScore,
            inv.isFlagged,
            inv.carrier,
            inv.trackingNumber,
            inv.createdAt
        );
    }

    /**
     * @notice Returns total number of registered invoices.
     */
    function getInvoiceCount() external view returns (uint256) {
        return allInvoiceIds.length;
    }

    /**
     * @notice Returns array of all invoice IDs.
     */
    function getAllInvoiceIds() external view returns (string[] memory) {
        return allInvoiceIds;
    }
}
