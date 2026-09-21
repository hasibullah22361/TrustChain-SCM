const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("==================================================");
  console.log("TrustChain SCM - Deploying SupplyChainFinance Contract");
  console.log("==================================================");

  const [deployer, supplier, buyer, lender] = await hre.ethers.getSigners();
  console.log("Deployer account:", deployer.address);
  console.log("Supplier account:", supplier.address);
  console.log("Buyer account:   ", buyer.address);
  console.log("Lender account:  ", lender.address);

  const SupplyChainFinance = await hre.ethers.getContractFactory("SupplyChainFinance");
  const contract = await SupplyChainFinance.deploy();
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  console.log("SupplyChainFinance deployed to:", contractAddress);

  // Export contract deployment info for listener and dashboard
  const deployInfo = {
    address: contractAddress,
    network: hre.network.name,
    deployedAt: new Date().toISOString(),
    accounts: {
      deployer: deployer.address,
      supplier: supplier.address,
      buyer: buyer.address,
      lender: lender.address,
    },
  };

  const outputPath = path.join(__dirname, "../deployment_info.json");
  fs.writeFileSync(outputPath, JSON.stringify(deployInfo, null, 2));
  console.log("Deployment details saved to:", outputPath);

  return { contract, contractAddress, deployer, supplier, buyer, lender };
}

if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}

module.exports = main;
