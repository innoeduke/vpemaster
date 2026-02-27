import click
from flask.cli import with_appcontext
from app.services.blockchain_service import BlockchainService

@click.command('deploy')
@with_appcontext
def deploy_contract():
    """Deploy the LevelTracker smart contract to Sepolia."""
    click.echo('Deploying LevelTracker contract...')
    try:
        contract_address = BlockchainService.deploy_contract()
        click.echo(f'\nSuccess! Contract deployed to: {contract_address}')
        click.echo(f'IMPORTANT: Update your .env file with:')
        click.echo(f'LEVEL_TRACKER_CONTRACT_ADDRESS={contract_address}\n')
    except Exception as e:
        click.echo(f"\nDeployment failed: {e}")
        exit(1)
